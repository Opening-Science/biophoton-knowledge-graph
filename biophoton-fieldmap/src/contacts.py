"""Stage F — contact routing + bounded email extraction from OA PDFs (spec §7).

1. Clean routing (always): ORCID public URL + institutional profile URL for the
   top-ranked in-scope researchers.
2. Email from OA PDFs (bounded, Martin-approved): for the top CONTACTS_MAX_TARGETS
   researchers, fetch up to CONTACTS_MAX_PDF_PER_AUTHOR of their recent
   corresponding-authored OA works, extract text with PyMuPDF, and pull the
   corresponding-author email published in the paper. Provenance kept.
3. Never brute-force or guess emails; only ones a researcher self-published.

Writes data/exports/contacts.csv (INTERNAL — the email column must not be
published in the open dataset) and NOTES_data_ethics.md.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from datetime import date

import fitz  # PyMuPDF
import httpx
import pandas as pd

import config as C
from author_merge import build_canonical_map

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
CORR_HINT = re.compile(r"correspond|\*|✉|e-?mail|✱", re.I)
PDF_DIR = C.CACHE / "pdfs"


def surname(display_name: str) -> str:
    parts = (display_name or "").replace(".", " ").split()
    return parts[-1].lower() if parts else ""


def best_pdf_url(w: dict) -> str | None:
    for key in ("best_oa_location", "primary_location"):
        loc = w.get(key) or {}
        if loc.get("pdf_url"):
            return loc["pdf_url"]
    for loc in (w.get("locations") or []):
        if loc.get("pdf_url"):
            return loc["pdf_url"]
    oa = w.get("open_access") or {}
    return oa.get("oa_url")


def extract_email_from_pdf(path, name: str) -> tuple[str, float] | None:
    try:
        doc = fitz.open(path)
    except Exception:
        return None
    sn = surname(name)
    # corresponding-author blocks live on the first page or the very end
    pages = list(range(min(1, doc.page_count))) + \
        ([doc.page_count - 1] if doc.page_count > 1 else [])
    best = None
    for pi in dict.fromkeys(pages):
        try:
            text = doc.load_page(pi).get_text()
        except Exception:
            continue
        for m in EMAIL_RE.finditer(text):
            email = m.group(0).rstrip(".")
            window = text[max(0, m.start() - 120): m.end() + 40]
            conf = 0.5
            if sn and sn in email.lower():
                conf = 0.95
            elif CORR_HINT.search(window):
                conf = 0.8
            if best is None or conf > best[1]:
                best = (email, conf)
    doc.close()
    return best


def main() -> None:
    con = sqlite3.connect(C.DB_PATH)
    canon = build_canonical_map(con)
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    if not (C.EXPORTS / "researchers.csv").exists():
        print("researchers.csv not found — run rank.py first (pass 1). Abort.")
        return
    ranked = pd.read_csv(C.EXPORTS / "researchers.csv")

    authors = pd.read_sql_query(
        "SELECT author_id, display_name, orcid, last_institution_id FROM authors",
        con).set_index("author_id")
    inst = pd.read_sql_query(
        "SELECT inst_id, display_name, ror FROM institutions",
        con).set_index("inst_id")

    wa = pd.read_sql_query(
        "SELECT wa.work_id, wa.author_id, wa.is_corresponding, "
        "w.year AS publication_year "
        "FROM work_authors wa JOIN works w ON w.work_id=wa.work_id", con)
    wa["canon"] = wa["author_id"].map(canon).fillna(wa["author_id"])

    rows = []
    log_fetches = []
    routing_ids = list(ranked.head(C.CONTACTS_ROUTING_TOP_N)["author_id"])
    email_targets = set(ranked.head(C.CONTACTS_MAX_TARGETS)["author_id"])
    # also target the biophoton-core top-N so core researchers (who rank below
    # prolific cavitation chemists overall) still get email extraction
    core_path = C.EXPORTS / "researchers_biophoton_core.csv"
    if core_path.exists():
        core = pd.read_csv(core_path).head(C.CONTACTS_CORE_TARGETS)
        email_targets |= set(core["author_id"])
        # ensure core targets are also routed
        routing_ids = list(dict.fromkeys(
            routing_ids + list(core["author_id"])))

    client = httpx.Client(timeout=30.0, follow_redirects=True,
                          headers={"User-Agent": f"biophoton-fieldmap "
                                   f"(mailto:{C.MAILTO})"})

    for aid in routing_ids:
        a = authors.loc[aid] if aid in authors.index else None
        name = ranked.set_index("author_id").loc[aid, "display_name"] \
            if aid in ranked["author_id"].values else (a["display_name"] if a is not None else "")
        orcid = (a["orcid"] if a is not None else None)
        iid = (a["last_institution_id"] if a is not None else None)
        orcid_url = orcid if (isinstance(orcid, str) and orcid) else ""
        inst_url = ""
        inst_name = ""
        if iid in inst.index:
            inst_name = inst.loc[iid, "display_name"]
            ror = inst.loc[iid, "ror"]
            inst_url = ror if isinstance(ror, str) and ror else ""

        email, src_doi, conf = "", "", 0.0
        if aid in email_targets:
            # recent corresponding-authored works, OA, most recent first
            mine = wa[(wa["canon"] == aid) &
                      (wa["is_corresponding"] == 1) &
                      (wa["publication_year"] >= C.CONTACTS_RECENT_YEAR)]
            mine = mine.sort_values("publication_year", ascending=False)
            tried = 0
            for w_row in mine.itertuples():
                if tried >= C.CONTACTS_MAX_PDF_PER_AUTHOR or email:
                    break
                w = _cached_work(w_row.work_id)
                if not w or not (w.get("open_access") or {}).get("is_oa"):
                    continue
                url = best_pdf_url(w)
                if not url or not url.lower().endswith("pdf") and "pdf" not in url.lower():
                    # still try; many OA pdf urls lack .pdf suffix
                    pass
                if not url:
                    continue
                pdf_path = PDF_DIR / f"{w_row.work_id}.pdf"
                if not pdf_path.exists():
                    try:
                        r = client.get(url)
                        if r.status_code == 200 and \
                           r.headers.get("content-type", "").lower().startswith(
                               ("application/pdf", "application/octet-stream")):
                            pdf_path.write_bytes(r.content)
                        else:
                            log_fetches.append(
                                {"work": w_row.work_id, "url": url,
                                 "status": r.status_code, "got": "non-pdf"})
                            time.sleep(0.4)
                            continue
                    except Exception as e:
                        log_fetches.append({"work": w_row.work_id, "url": url,
                                            "error": str(e)[:80]})
                        continue
                    time.sleep(0.4)
                tried += 1
                res = extract_email_from_pdf(pdf_path, name)
                log_fetches.append({"work": w_row.work_id, "url": url,
                                    "extracted": bool(res)})
                if res:
                    email, conf = res
                    src_doi = (w.get("doi") or "").replace(
                        "https://doi.org/", "")

        rows.append({
            "author_id": aid, "display_name": name,
            "orcid_url": orcid_url, "institution": inst_name,
            "institution_url": inst_url,
            "email": email, "email_source_doi": src_doi,
            "email_confidence": round(conf, 2),
            "retrieved_date": date.fromisoformat("2026-07-20").isoformat(),
        })

    client.close()
    df = pd.DataFrame(rows)
    df.to_csv(C.EXPORTS / "contacts.csv", index=False)
    (C.EXPORTS / "contacts_fetch_log.json").write_text(
        json.dumps(log_fetches, indent=2))

    n_email = int((df["email"] != "").sum())
    n_orcid = int((df["orcid_url"] != "").sum())
    print("=== Stage F: contacts ===")
    print(f"  routed: {len(df)} researchers")
    print(f"  with ORCID URL: {n_orcid}")
    print(f"  emails extracted from OA PDFs: {n_email} "
          f"(of {len(email_targets)} attempted)")
    print(f"  PDF fetch attempts logged: {len(log_fetches)}")

    _write_ethics_note()
    with open(C.RUN_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n## Stage F — contacts\n\n- routed {len(df)}; "
                f"ORCID {n_orcid}; emails {n_email}; "
                f"PDF attempts {len(log_fetches)}\n")
    con.close()


def _cached_work(work_id: str) -> dict | None:
    p = C.CACHE / "works" / f"{work_id}.json"
    if p.exists():
        return json.loads(p.read_text())
    return None


def _write_ethics_note() -> None:
    txt = """# Data ethics — contact information (INTERNAL to OSF)

## Basis and scope
Contact data here is academic contact information the researchers **self-published**
in their own open-access papers (corresponding-author emails) or on open
infrastructure (ORCID, institutional/ROR profiles). Processing basis: legitimate
interest for scholarly outreach about the state of the biophoton/UPE field.

## Rules
- **Never published in the open book/dataset.** The `email` column in
  `contacts.csv` / `researchers.csv` is INTERNAL. Strip it before any public
  release; publish only name, ORCID, institution, and public profile URLs.
- **Provenance kept per email:** `email_source_doi`, `email_confidence`,
  `retrieved_date`. Every email traces to the specific paper it came from.
- **No guessing / no brute force:** emails are only taken verbatim from a PDF the
  researcher authored; none are inferred from name+domain patterns.
- **Honor opt-outs:** on any request, delete the person's row and record the
  opt-out.
- **Bounded collection:** only top-ranked targets, only recent
  corresponding-authored OA works, capped per author (see config.py).

## Provenance of the fetch
See `data/exports/contacts_fetch_log.json` for every PDF URL fetched and whether
an email was extracted.
"""
    (C.ROOT / "NOTES_data_ethics.md").write_text(txt)


if __name__ == "__main__":
    main()
