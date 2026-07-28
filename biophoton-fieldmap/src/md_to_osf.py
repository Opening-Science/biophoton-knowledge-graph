"""Convert a project markdown report into an OSF board-report config JSON.

Parses headings / lists / tables / paragraphs into the skill's config schema and
enforces the OSF house style: no em/en dashes (ranges become "A to B", lead
separators become ": ", other dashes become ", "), no arrows or block glyphs,
markdown emphasis normalized (keep **bold**, strip italics/links/backticks).

Usage: python md_to_osf.py <input.md> <output_config.json> <meta_key>
where meta_key selects a metadata preset defined below.
"""
from __future__ import annotations

import json
import re
import sys

# ---- per-report metadata presets (title/subtitle/info block) -------------
PRESETS = {
    "field_state": {
        "title": "The Biophoton and Ultra-Weak Photon Emission Field",
        "subtitle": "State of the field. A structured map for the OSF open-science book.",
        "metadata": {
            "Title": "State of the Biophoton / UPE Field (RPT-2026-BPH-001)",
            "Author": "Martin Etzrodt, Open Science Institute",
            "Subject": "State-of-field map, biophoton / UPE research"},
        "info": [
            {"label": "Date", "value": "20 July 2026"},
            {"label": "Prepared by", "value": "Martin Etzrodt, Director, Open Science Institute"},
            {"label": "Distribution", "value": "OSF Foundation Council"},
            {"label": "Reference", "value": "RPT-2026-BPH-001 · PRJ-BIOPHOTON"},
            {"label": "Source", "value": "OpenAlex snapshot, July 2026. fieldmap.sqlite."},
        ],
    },
    "field_boundary": {
        "title": "Biophoton Field Map: Milestone 2 Checkpoint",
        "subtitle": "Cluster map, field-boundary result, and verification.",
        "metadata": {
            "Title": "Biophoton Field Map, Milestone 2 (RPT-2026-BPH-002)",
            "Author": "Martin Etzrodt, Open Science Institute",
            "Subject": "Field boundary and cluster verification"},
        "info": [
            {"label": "Date", "value": "20 July 2026"},
            {"label": "Prepared by", "value": "Martin Etzrodt, Director, Open Science Institute"},
            {"label": "Distribution", "value": "OSF Foundation Council"},
            {"label": "Reference", "value": "RPT-2026-BPH-002 · PRJ-BIOPHOTON"},
        ],
    },
    "open_plan": {
        "title": "Open Resource Release Plan",
        "subtitle": "Releasing the biophoton field map as an open, living community resource.",
        "metadata": {
            "Title": "Open Resource Release Plan, Biophoton Field Map (RPT-2026-BPH-006)",
            "Author": "Martin Etzrodt, Open Science Institute",
            "Subject": "Open-data release plan for the biophoton field map"},
        "info": [
            {"label": "Date", "value": "21 July 2026"},
            {"label": "Prepared by", "value": "Martin Etzrodt, Director, Open Science Institute"},
            {"label": "Distribution", "value": "OSF Foundation Council"},
            {"label": "Reference", "value": "RPT-2026-BPH-006 · PRJ-BIOPHOTON"},
            {"label": "Decisions", "value": "CC0 license. Inverted-index abstracts. Living, refreshed resource."},
        ],
    },
    "interview": {
        "title": "Author and Interview List by Sub-field",
        "subtitle": "Recommended researchers to cite and interview, grouped by sub-field.",
        "metadata": {
            "Title": "Author and Interview List, Biophoton / UPE (RPT-2026-BPH-005)",
            "Author": "Martin Etzrodt, Open Science Institute",
            "Subject": "Researcher outreach shortlist by sub-field"},
        "info": [
            {"label": "Date", "value": "20 July 2026"},
            {"label": "Prepared by", "value": "Martin Etzrodt, Director, Open Science Institute"},
            {"label": "Distribution", "value": "OSF Foundation Council"},
            {"label": "Reference", "value": "RPT-2026-BPH-005 · PRJ-BIOPHOTON"},
            {"label": "Note", "value": "Public routing only. Emails held in the internal contacts dataset."},
        ],
    },
    "book_reco": {
        "title": "Book Chapter Recommendation",
        "subtitle": "Proposed chapter structure for the OSF biophoton / UPE book.",
        "metadata": {
            "Title": "Book Chapter Recommendation, Biophoton / UPE Book (RPT-2026-BPH-004)",
            "Author": "Martin Etzrodt, Open Science Institute",
            "Subject": "Recommended chapter structure for the OSF open-science book"},
        "info": [
            {"label": "Date", "value": "20 July 2026"},
            {"label": "Prepared by", "value": "Martin Etzrodt, Director, Open Science Institute"},
            {"label": "Distribution", "value": "OSF Foundation Council"},
            {"label": "Reference", "value": "RPT-2026-BPH-004 · PRJ-BIOPHOTON"},
            {"label": "Evidence base", "value": "Field map: fieldmap.sqlite, OpenAlex snapshot July 2026."},
        ],
    },
    "community0": {
        "title": "Inside the Biophoton Core",
        "subtitle": "Subdivision of the core community into research strands.",
        "metadata": {
            "Title": "Biophoton Core Subdivision (RPT-2026-BPH-003)",
            "Author": "Martin Etzrodt, Open Science Institute",
            "Subject": "Community 0 subdivision into UPE strands"},
        "info": [
            {"label": "Date", "value": "20 July 2026"},
            {"label": "Prepared by", "value": "Martin Etzrodt, Director, Open Science Institute"},
            {"label": "Distribution", "value": "OSF Foundation Council"},
            {"label": "Reference", "value": "RPT-2026-BPH-003 · PRJ-BIOPHOTON"},
            {"label": "Method", "value": "Leiden clustering at resolution 3.0 on the coupling subgraph."},
        ],
    },
}


# ---- inline text sanitizer (OSF house style) -----------------------------
def sanitize(text: str, lead: bool = False) -> str:
    t = text.strip()
    # strip stray HTML tags (OpenAlex titles carry <i>, <sub>, etc.)
    t = re.sub(r"</?[a-zA-Z][^>]*>", "", t)
    # markdown links [label](url) -> label
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    # backticks / code
    t = t.replace("`", "")
    # arrows with a bold tag: " <- **X**" -> " (X)"
    t = re.sub(r"\s*[←→⬅➤]\s*\*\*(.+?)\*\*", r" (\1)", t)
    t = re.sub(r"\s*[←→⬅➤]\s*", " ", t)
    # block glyphs (ascii bar chart), checkmarks
    t = t.replace("█", "").replace("✓", "yes").replace("✗", "no")
    # year ranges only (4-digit to 4-digit) with a long dash -> "A to B"
    t = re.sub(r"(\b\d{4})\s*[—–]\s*(\d{4}\b)", r"\1 to \2", t)
    # a lead separator (first remaining long dash) -> colon; else comma
    if lead and re.search(r"\s[—–]\s", t):
        t = re.sub(r"\s*[—–]\s*", ": ", t, count=1)
    t = re.sub(r"\s*[—–]\s*", ", ", t)
    # italics: _x_ or single *x* (leave ** bold intact)
    t = re.sub(r"(?<!\*)\*(?!\*)([^*]+?)\*(?!\*)", r"\1", t)
    t = re.sub(r"(?<![A-Za-z0-9])_([^_]+?)_(?![A-Za-z0-9])", r"\1", t)
    # collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


def strip_md_head(line: str) -> tuple[int, str]:
    m = re.match(r"^(#{1,6})\s+(.*)$", line)
    if m:
        return len(m.group(1)), m.group(2).strip()
    return 0, line


def parse(md: str) -> list[dict]:
    lines = md.split("\n")
    sections: list[dict] = []
    cur = {"label": "Summary", "blocks": []}
    sections_started = False
    i = 0
    para: list[str] = []
    ul: list = []

    def flush_para():
        nonlocal para
        if para:
            txt = sanitize(" ".join(para))
            if txt:
                cur["blocks"].append(txt)
            para = []

    def flush_ul():
        nonlocal ul
        if ul:
            cur["blocks"].append({"type": "ul", "items": ul})
            ul = []

    def push_section():
        nonlocal cur
        if cur["blocks"] or cur is not None:
            sections.append(cur)

    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        level, text = strip_md_head(line)

        # skip code fences entirely
        if line.strip().startswith("```"):
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                i += 1
            i += 1
            continue

        if level == 1:
            # document title handled by preset; skip
            flush_para(); flush_ul()
            i += 1
            continue
        if level == 2:
            flush_para(); flush_ul()
            if sections_started or cur["blocks"]:
                sections.append(cur)
            cur = {"label": sanitize(text, lead=True), "blocks": []}
            sections_started = True
            i += 1
            continue
        if level in (3, 4, 5, 6):
            flush_para(); flush_ul()
            cur["blocks"].append({"type": "p", "tight": True,
                                  "lead": sanitize(text, lead=True) + ".",
                                  "text": ""})
            i += 1
            continue

        # markdown table
        if line.lstrip().startswith("|") and "|" in line:
            flush_para(); flush_ul()
            tbl_lines = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                tbl_lines.append(lines[i].strip())
                i += 1
            cur["blocks"].append(parse_table(tbl_lines))
            continue

        # list item
        m = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if m:
            flush_para()
            indent = len(m.group(1))
            item = sanitize(m.group(2), lead=True)
            if indent >= 2 and ul:
                last = ul[-1]
                if isinstance(last, str):
                    ul[-1] = {"text": last, "sub": [item]}
                else:
                    last.setdefault("sub", []).append(item)
            else:
                ul.append(item)
            i += 1
            continue

        # continuation of the current list item (indented, no bullet marker)
        if ul and line[:1] in (" ", "\t") and line.strip():
            cont = sanitize(line.strip())
            last = ul[-1]
            if isinstance(last, str):
                ul[-1] = (last + " " + cont).strip()
            else:
                last["text"] = (last.get("text", "") + " " + cont).strip()
            i += 1
            continue

        # blank line
        if not line.strip():
            flush_para(); flush_ul()
            i += 1
            continue

        # ordinary paragraph text (may be blockquote). Skip a standalone,
        # fully-italic provenance line (auto-generated note duplicated by info).
        flush_ul()
        body = line.strip().lstrip(">").strip()
        if re.match(r"^_.+_$", body):
            i += 1
            continue
        para.append(body)
        i += 1

    flush_para(); flush_ul()
    sections.append(cur)
    # drop empty leading section
    sections = [s for s in sections if s["blocks"]]
    return sections


def parse_table(tbl_lines: list[str]) -> dict:
    rows = []
    for ln in tbl_lines:
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        rows.append(cells)
    # drop separator row like |---|---|
    rows = [r for r in rows if not all(re.match(r"^:?-{2,}:?$", c or "-") for c in r)]
    cols = [sanitize(c) for c in rows[0]] if rows else []
    data = [[sanitize(c) for c in r] for r in rows[1:]]
    return {"type": "table", "columns": cols, "first_col_bold": True, "rows": data}


def main():
    inp, outp, key = sys.argv[1], sys.argv[2], sys.argv[3]
    md = open(inp, encoding="utf-8").read()
    preset = PRESETS[key]
    cfg = {
        "title": preset["title"],
        "subtitle": preset["subtitle"],
        "metadata": preset["metadata"],
        "info": preset["info"],
        "auto_attachments_row": False,
        "auto_attachments_section": False,
        "sections": parse(md),
        "attachments": [],
    }
    json.dump(cfg, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    # dash audit
    blob = json.dumps(cfg, ensure_ascii=False)
    bad = sum(blob.count(c) for c in ("—", "–"))
    print(f"Wrote {outp}: {len(cfg['sections'])} sections, "
          f"{'NO long dashes' if bad == 0 else str(bad)+' LONG DASHES REMAIN'}")


if __name__ == "__main__":
    main()
