"""Build a DOI-keyed database of each interview-list author's relevant in-field
papers, with abstracts. No PDFs are downloaded.

For every author on the by-sub-field interview list, take their most relevant
works in the field universe (seeds first, then core-topic works, then by
citations, capped at MAX_PAPERS_PER_AUTHOR), attach the abstract (reconstructed
and cached during the openness stage), and record the DOI, OA status, and an
open link. Any missing abstract is fetched once from OpenAlex.

Outputs under outputs/papers/:
  author_papers.sqlite   papers table (unique works) + author_papers link table
  author_papers.csv      denormalized author/paper/abstract rows
"""
from __future__ import annotations

import json
import sqlite3

import pandas as pd

import config as C
from author_merge import build_canonical_map
from interview_list import SUBFIELDS
from openalex import OpenAlex, oa_short_id

MAX_PAPERS_PER_AUTHOR = 25          # papers per author
AUTHORS_PER_SUBFIELD = 20           # top 20 authors per sub-field
ABS_CACHE = C.CACHE / "abstracts"
OUT_DB = C.OUTPUTS / "papers" / "author_papers.sqlite"
OUT_CSV = C.OUTPUTS / "papers" / "author_papers.csv"
CORE_HINTS = C.CORE_TOPIC_HINTS


def read_abstract(wid: str) -> str:
    p = ABS_CACHE / f"{wid}.json"
    if p.exists():
        try:
            return json.loads(p.read_text()) or ""
        except Exception:
            return ""
    return ""


def cached_work(wid: str) -> dict | None:
    p = C.CACHE / "works" / f"{wid}.json"
    return json.loads(p.read_text()) if p.exists() else None


def paper_link(w: dict | None, doi: str) -> str:
    if doi:
        return doi if doi.startswith("http") else f"https://doi.org/{doi}"
    if w:
        pl = (w.get("primary_location") or {}).get("landing_page_url")
        if pl:
            return pl
        return w.get("id") or ""
    return ""


def author_targets() -> pd.DataFrame:
    r = pd.read_csv(C.EXPORTS / "researchers.csv")
    picks = []
    for comm, name, desc, _n in SUBFIELDS:
        sub = r[(r["community"] == comm) &
                (r.get("consciousness_adjacent", 0) != 1)] \
            .head(AUTHORS_PER_SUBFIELD).copy()
        sub["subfield"] = name
        picks.append(sub)
    ca = r[r.get("consciousness_adjacent", 0) == 1].head(12).copy()
    ca["subfield"] = "Consciousness-adjacent"
    picks.append(ca)
    return pd.concat(picks, ignore_index=True).drop_duplicates("author_id")


def relevant_works(con, canon, author_id: str) -> pd.DataFrame:
    raw_ids = [a for a, c in canon.items() if c == author_id] or [author_id]
    qmarks = ",".join("?" * len(raw_ids))
    rows = pd.read_sql_query(
        f"SELECT DISTINCT w.work_id, w.title, w.year, w.doi, w.cited_by_count, "
        f"w.is_seed, w.oa_status, w.is_oa, w.hop "
        f"FROM works w JOIN work_authors wa ON wa.work_id=w.work_id "
        f"WHERE wa.author_id IN ({qmarks})", con, params=raw_ids)
    if rows.empty:
        return rows
    topics = pd.read_sql_query("SELECT work_id, topic_name FROM topics", con)
    core = set(topics[topics["topic_name"].str.lower().fillna("").apply(
        lambda t: any(h in t for h in CORE_HINTS))]["work_id"])
    rows["core"] = rows["work_id"].isin(core).astype(int)
    rows["score"] = (rows["is_seed"] * 1000 + rows["core"] * 100 +
                     rows["cited_by_count"].fillna(0))
    return rows.sort_values("score", ascending=False).head(MAX_PAPERS_PER_AUTHOR)


def main():
    con = sqlite3.connect(C.DB_PATH)
    canon = build_canonical_map(con)
    targets = author_targets()
    print(f"{len(targets)} interview-list authors, cap "
          f"{MAX_PAPERS_PER_AUTHOR} papers/author")

    rows = []
    for t in targets.itertuples():
        works = relevant_works(con, canon, t.author_id)
        for w in works.itertuples():
            doi = (w.doi or "").replace("https://doi.org/", "")
            wk = cached_work(w.work_id)
            rows.append({
                "subfield": t.subfield,
                "author": str(t.display_name),
                "author_orcid": (str(t.orcid).replace("https://orcid.org/", "")
                                 if pd.notna(t.orcid) else ""),
                "author_id": t.author_id,
                "work_id": w.work_id,
                "doi": doi,
                "title": w.title or "",
                "year": int(w.year) if pd.notna(w.year) else None,
                "oa_status": w.oa_status or "closed",
                "is_oa": int(bool(w.is_oa)),
                "cited_by_count": int(w.cited_by_count or 0),
                "is_seed": int(w.is_seed),
                "abstract": read_abstract(w.work_id),
                "openalex_url": f"https://openalex.org/{w.work_id}",
                "link": paper_link(wk, doi),
            })
    con.close()

    df = pd.DataFrame(rows)

    # fetch any missing abstracts once (should be rare; universe abstracts are
    # already cached from the openness stage)
    missing = df[(df["abstract"] == "")]["work_id"].unique().tolist()
    n_absent = len(missing)
    if missing:
        from openness import reconstruct_abstract
        oa = OpenAlex()
        ABS_CACHE.mkdir(parents=True, exist_ok=True)
        for i in range(0, len(missing), 50):
            batch = missing[i:i + 50]
            for wk in oa.paged("works", "openalex_id:" + "|".join(batch),
                               select="id,abstract_inverted_index"):
                sid = oa_short_id(wk["id"])
                txt = reconstruct_abstract(wk.get("abstract_inverted_index"))
                (ABS_CACHE / f"{sid}.json").write_text(json.dumps(txt))
        oa.close()
        df["abstract"] = df["work_id"].map(lambda w: read_abstract(w))

    n_with_abs = int((df["abstract"].str.len() > 0).sum())

    # write SQLite: papers (unique) + author_papers (link)
    OUT_DB.parent.mkdir(parents=True, exist_ok=True)
    if OUT_DB.exists():
        OUT_DB.unlink()
    db = sqlite3.connect(OUT_DB)
    papers = (df.drop(columns=["subfield", "author", "author_orcid", "author_id"])
              .drop_duplicates("work_id"))
    papers.to_sql("papers", db, index=False)
    df[["author", "author_orcid", "author_id", "subfield", "work_id",
        "doi", "year"]].to_sql("author_papers", db, index=False)
    db.executescript(
        "CREATE INDEX idx_papers_doi ON papers(doi);"
        "CREATE INDEX idx_papers_work ON papers(work_id);"
        "CREATE INDEX idx_ap_author ON author_papers(author_id);"
        "CREATE INDEX idx_ap_work ON author_papers(work_id);")

    # full-text search index over title + abstract (+ doi for lookup)
    fts_ok = True
    try:
        db.executescript(
            "CREATE VIRTUAL TABLE papers_fts USING fts5("
            "  work_id UNINDEXED, doi UNINDEXED, title, abstract);"
            "INSERT INTO papers_fts (work_id, doi, title, abstract) "
            "  SELECT work_id, doi, title, abstract FROM papers;")
    except sqlite3.OperationalError as e:
        fts_ok = False
        print(f"  NOTE: FTS5 unavailable in this sqlite build ({e}); "
              f"skipped the search index.")
    db.commit()
    n_fts = db.execute("SELECT COUNT(*) FROM papers_fts").fetchone()[0] if fts_ok else 0
    db.close()

    df.to_csv(OUT_CSV, index=False)

    print("=== build_paper_db ===")
    print(f"  authors: {len(targets)} (top {AUTHORS_PER_SUBFIELD}/sub-field)")
    print(f"  author/paper rows: {len(df)}")
    print(f"  unique papers: {papers['work_id'].nunique()}")
    print(f"  unique DOIs: {(papers['doi'] != '').sum()}")
    print(f"  papers with abstract: {n_with_abs}/{len(df)} rows "
          f"({n_absent} works were missing, fetched)")
    print(f"  full-text index rows: {n_fts}")
    print(f"  wrote {OUT_DB.name} + {OUT_CSV.name}")


if __name__ == "__main__":
    main()
