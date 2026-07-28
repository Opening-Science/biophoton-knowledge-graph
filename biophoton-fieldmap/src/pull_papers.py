"""Pull each interview-list author's relevant (in-field) papers from OpenAlex.

For every author on the by-sub-field interview list, take their most relevant
works in the field universe (seeds first, then core-topic works, then by
citations), download the open-access PDF where one exists, and record a link
(DOI, else landing page, else OpenAlex) where the paper is closed.

Outputs under outputs/papers/:
  <Author_Slug>/<year>_<workid>.pdf   downloaded OA PDFs
  papers_manifest.csv                 every paper: author, work, oa, local/link
  reading_list.md                     readable index grouped by sub-field/author
"""
from __future__ import annotations

import csv
import json
import re
import sqlite3
import time
from pathlib import Path

import httpx
import pandas as pd
from unidecode import unidecode

import config as C
from author_merge import build_canonical_map
from interview_list import SUBFIELDS

MAX_PAPERS_PER_AUTHOR = 5
MAX_PDF_BYTES = 40 * 1024 * 1024
PAPERS_DIR = C.OUTPUTS / "papers"
CORE_HINTS = C.CORE_TOPIC_HINTS


def slug(name: str) -> str:
    s = unidecode(name or "author").strip()
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")
    return s or "author"


def cached_work(wid: str) -> dict | None:
    p = C.CACHE / "works" / f"{wid}.json"
    return json.loads(p.read_text()) if p.exists() else None


def best_pdf_url(w: dict) -> str | None:
    for key in ("best_oa_location", "primary_location"):
        loc = w.get(key) or {}
        if loc.get("pdf_url"):
            return loc["pdf_url"]
    for loc in (w.get("locations") or []):
        if loc.get("pdf_url"):
            return loc["pdf_url"]
    return (w.get("open_access") or {}).get("oa_url")


def closed_link(w: dict) -> str:
    doi = w.get("doi")
    if doi:
        return doi if doi.startswith("http") else f"https://doi.org/{doi}"
    pl = (w.get("primary_location") or {}).get("landing_page_url")
    if pl:
        return pl
    return w.get("id") or ""


def author_targets() -> pd.DataFrame:
    r = pd.read_csv(C.EXPORTS / "researchers.csv")
    picks = []
    for comm, name, desc, n in SUBFIELDS:
        sub = r[(r["community"] == comm) &
                (r.get("consciousness_adjacent", 0) != 1)].head(n).copy()
        sub["subfield"] = name
        picks.append(sub)
    ca = r[r.get("consciousness_adjacent", 0) == 1].head(8).copy()
    ca["subfield"] = "Consciousness-adjacent"
    picks.append(ca)
    out = pd.concat(picks, ignore_index=True)
    return out.drop_duplicates("author_id")


def relevant_works(con, canon, author_id: str) -> list[dict]:
    # every in-universe work by any raw id mapping to this canonical author
    raw_ids = [a for a, c in canon.items() if c == author_id] or [author_id]
    qmarks = ",".join("?" * len(raw_ids))
    rows = pd.read_sql_query(
        f"SELECT DISTINCT w.work_id, w.title, w.year, w.doi, w.cited_by_count, "
        f"w.is_seed, w.oa_status, w.is_oa "
        f"FROM works w JOIN work_authors wa ON wa.work_id=w.work_id "
        f"WHERE wa.author_id IN ({qmarks})", con, params=raw_ids)
    if rows.empty:
        return []
    topics = pd.read_sql_query(
        "SELECT work_id, topic_name FROM topics", con)
    core_works = set(topics[topics["topic_name"].str.lower().fillna("").apply(
        lambda t: any(h in t for h in CORE_HINTS))]["work_id"])
    rows["core"] = rows["work_id"].isin(core_works).astype(int)
    rows["score"] = (rows["is_seed"] * 1000 + rows["core"] * 100 +
                     rows["cited_by_count"].fillna(0))
    rows = rows.sort_values("score", ascending=False).head(MAX_PAPERS_PER_AUTHOR)
    return rows.to_dict("records")


def main():
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(C.DB_PATH)
    canon = build_canonical_map(con)
    targets = author_targets()
    print(f"{len(targets)} interview-list authors")

    client = httpx.Client(timeout=30.0, follow_redirects=True,
                          headers={"User-Agent": f"biophoton-fieldmap "
                                   f"(mailto:{C.MAILTO})"})
    manifest = []
    n_pdf = n_link = 0

    for t in targets.itertuples():
        aid = t.author_id
        name = str(t.display_name)
        adir = PAPERS_DIR / slug(name)
        works = relevant_works(con, canon, aid)
        if not works:
            continue
        for rec in works:
            wid = rec["work_id"]
            w = cached_work(wid)
            oa = bool(rec.get("is_oa"))
            doi = rec.get("doi") or ""
            local = ""
            link = ""
            url = best_pdf_url(w) if w else None
            if oa and url:
                adir.mkdir(parents=True, exist_ok=True)
                dest = adir / f"{rec.get('year') or 'n.d.'}_{wid}.pdf"
                if dest.exists():
                    local = str(dest.relative_to(C.OUTPUTS))
                    n_pdf += 1
                else:
                    try:
                        resp = client.get(url)
                        content = resp.content
                        # PDF magic bytes are authoritative; some OA hosts serve
                        # a real PDF with a wrong/blank content-type.
                        is_pdf = (resp.status_code == 200 and
                                  content[:5] == b"%PDF-" and
                                  len(content) <= MAX_PDF_BYTES)
                        if is_pdf:
                            dest.write_bytes(content)
                            local = str(dest.relative_to(C.OUTPUTS))
                            n_pdf += 1
                        else:
                            link = closed_link(w) if w else (
                                f"https://doi.org/{doi}" if doi else "")
                        time.sleep(0.4)
                    except Exception:
                        link = closed_link(w) if w else ""
            else:
                link = closed_link(w) if w else (
                    f"https://doi.org/{doi}" if doi else "")
            if not local and link:
                n_link += 1
            manifest.append({
                "subfield": t.subfield, "author": name,
                "orcid": (str(t.orcid).replace("https://orcid.org/", "")
                          if pd.notna(t.orcid) else ""),
                "work_id": wid, "title": rec.get("title") or "",
                "year": rec.get("year") or "", "doi": doi.replace("https://doi.org/", ""),
                "oa_status": rec.get("oa_status") or "closed",
                "local_pdf": local, "link": link,
            })

    client.close()
    con.close()

    # manifest CSV
    with open(PAPERS_DIR / "papers_manifest.csv", "w", newline="",
              encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(manifest[0].keys()))
        wr.writeheader()
        wr.writerows(manifest)

    # readable index grouped by sub-field -> author
    L = ["# Reading list: relevant papers by author\n",
         f"Downloaded open-access PDFs live beside this file under "
         f"`papers/<Author>/`. Closed papers are given as links (DOI where "
         f"available). {n_pdf} PDFs downloaded, {n_link} links recorded.\n"]
    dfm = pd.DataFrame(manifest)
    for sf in dfm["subfield"].unique():
        L.append(f"## {sf}\n")
        for author in dfm[dfm["subfield"] == sf]["author"].unique():
            L.append(f"### {author}")
            for r in dfm[(dfm["subfield"] == sf) &
                         (dfm["author"] == author)].itertuples():
                title = (r.title or "")[:110]
                if r.local_pdf:
                    ref = f"[PDF]({r.local_pdf})"
                elif r.link:
                    ref = f"[link]({r.link})"
                else:
                    ref = "(no source)"
                doi = f" doi:{r.doi}" if r.doi else ""
                L.append(f"- {title} ({r.year}) {ref} [{r.oa_status}]{doi}")
            L.append("")
    (PAPERS_DIR / "reading_list.md").write_text("\n".join(L))

    print(f"=== pull_papers ===")
    print(f"  papers listed: {len(manifest)}")
    print(f"  OA PDFs downloaded: {n_pdf}")
    print(f"  links recorded (closed / non-pdf): {n_link}")
    print(f"  output: {PAPERS_DIR}")


if __name__ == "__main__":
    main()
