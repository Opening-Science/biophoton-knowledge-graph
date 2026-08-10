"""Join the full-text corpus to the field map in one queryable database.

Stage K. Everything book planning needs sits in four places -- the works/
authors/topics tables (fieldmap.sqlite), the clustering exports, the ranked
abstract index, and the extracted full text (fulltext.sqlite). This stage
denormalizes them into literature/knowledgebase.sqlite so a single query can
ask questions like "who are the most-published living authors in the human-UPE
strand whose papers we hold in full text, and what do those papers say is
unsolved?".

Tables:
  works           one row per work in the universe, with cluster, sub-strand,
                  rank score, abstract, full-text status and quality
  authors         canonical authors with openness, output, activity span
  work_authors    link table (canonical ids)
  statements      mined open-question/limitation/gap sentences (from stage J)
  chapter_map     the draft chapter structure as data: chapter -> anchor
                  cluster/sub-strand, so chapter-level queries are joins,
                  not prose
  works_fts       FTS5 over title+abstract+fulltext (porter-stemmed)

The chapter mapping mirrors outputs/book_chapter_recommendation.md; if the
chapter plan changes, edit CHAPTERS here and rebuild.
"""
from __future__ import annotations

import json
import sqlite3

import pandas as pd

import config as C

LIT = C.ROOT.parent / "literature"
FT_DB = LIT / "fulltext.sqlite"
KB = LIT / "knowledgebase.sqlite"
IDX_DB = C.OUTPUTS / "index" / "full_paper_index.sqlite"

# chapter -> (anchor kind, anchor ids). Communities are bibliographic-coupling
# communities; strands are the community-0 subdivision sub-clusters.
CHAPTERS = [
    ("1 What UPE is",              "strand",    [1]),
    ("2 Where the field ends",     "community", [1, 2, 4, 6]),
    ("3 The sub-fields",           "community", [0, 1, 2, 3, 4, 6]),
    ("4 Inside the core",          "community", [0]),
    ("5 The ROS connection",       "community", [3]),
    ("6 Consciousness-adjacent",   "strand",    [8]),
    ("7 Imaging and applications", "strand",    [3, 5]),
    ("8 Theory and coherence",     "strand",    [6, 7]),
    ("9 Open science and outlook", "community", []),   # cross-cutting
]


def load_communities() -> pd.DataFrame:
    """work_id -> cluster assignments, tolerant of the in-flight refactor.

    `community` is always the original coupling numbering (community 0 = UPE
    core, 3 = ROS, ...), which is what the chapter anchors, the subdivision,
    and every existing report reference. Where the v2 export exists, its CPM
    clustering rides along as `community_v2` (+ per-node `stability`) --
    finer-grained (UPE home there is v2 community 6), but not yet what the
    book documents are written against.
    """
    v2 = C.EXPORTS / "work_communities_v2.csv"
    if v2.exists():
        df = pd.read_csv(v2)
        cols = ["work_id", "coupling_community"]
        for extra in ("community_v2", "stability"):
            if extra in df.columns:
                cols.append(extra)
        print(f"  communities from {v2.name} ({', '.join(cols[1:])})")
        return df[cols].rename(columns={"coupling_community": "community"})
    for fname, col in (("work_communities_normalized.csv", "community_norm"),
                       ("work_communities.csv", "coupling_community")):
        path = C.EXPORTS / fname
        if path.exists():
            df = pd.read_csv(path)
            if col in df.columns:
                print(f"  communities from {fname}:{col}")
                return df[["work_id", col]].rename(columns={col: "community"})
    raise SystemExit("no clustering export found")


def main() -> None:
    if KB.exists():
        KB.unlink()
    out = sqlite3.connect(KB)

    # --- works ------------------------------------------------------------
    idx = sqlite3.connect(IDX_DB)
    works = pd.read_sql_query(
        "SELECT work_id, doi, title, authors, year, type, cited_by_count, "
        "link_count, primary_topic, core_topic, oa_status, is_oa, is_seed, "
        "hop, paper_rank_score, abstract, link FROM papers", idx)
    idx.close()

    works = works.merge(load_communities(), on="work_id", how="left")
    sub = pd.read_csv(C.EXPORTS / "community0_subclusters.csv")
    works = works.merge(sub.rename(columns={"subcluster": "core_strand"}),
                        on="work_id", how="left")

    ft = sqlite3.connect(FT_DB)
    fts = pd.read_sql_query(
        "SELECT work_id, file, n_pages, n_chars, quality, lang_guess "
        "FROM fulltext WHERE work_id != ''", ft)
    # a work can appear twice (harvested + curated copy); keep the best copy
    fts["q_rank"] = fts["quality"].map(
        {"ok": 0, "references-heavy": 1, "mostly-scanned": 2,
         "no-text-layer": 3}).fillna(4)
    fts = (fts.sort_values(["work_id", "q_rank"])
              .drop_duplicates("work_id")
              .drop(columns="q_rank")
              .rename(columns={"file": "fulltext_file",
                               "quality": "fulltext_quality"}))
    works = works.merge(fts, on="work_id", how="left")
    works["has_fulltext"] = works["fulltext_file"].notna().astype(int)
    works.to_sql("works", out, index=False)

    # --- authors ----------------------------------------------------------
    fm = sqlite3.connect(C.DB_PATH)
    from author_merge import build_canonical_map
    canon = build_canonical_map(fm)
    wa = pd.read_sql_query(
        "SELECT work_id, author_id, position, is_corresponding "
        "FROM work_authors", fm)
    wa["author_id"] = wa["author_id"].map(lambda a: canon.get(a, a))
    wa = wa.drop_duplicates(["work_id", "author_id"])
    wa.to_sql("work_authors", out, index=False)

    au = pd.read_sql_query(
        "SELECT a.author_id, a.display_name, a.orcid, a.works_count, "
        "a.cited_by_count, i.display_name AS institution, a.country "
        "FROM authors a LEFT JOIN institutions i "
        "ON i.inst_id = a.last_institution_id", fm)
    au["author_id"] = au["author_id"].map(lambda a: canon.get(a, a))
    au = au.sort_values("works_count", ascending=False) \
           .drop_duplicates("author_id")
    op = pd.read_parquet(C.EXPORTS / "author_openness.parquet")
    op["author_id"] = op["author_id"].map(lambda a: canon.get(a, a))
    op = op.drop_duplicates("author_id")
    au = au.merge(op[["author_id", "openness"]].rename(
        columns={"openness": "openness_score"}), on="author_id", how="left")
    # activity span inside the universe, for telling active from historical
    span = (wa.merge(works[["work_id", "year"]], on="work_id")
              .groupby("author_id")["year"].agg(["min", "max", "count"])
              .rename(columns={"min": "first_year", "max": "last_year",
                               "count": "n_works_universe"}))
    au = au.merge(span, on="author_id", how="left")
    au.to_sql("authors", out, index=False)

    # --- statements + chapter map ----------------------------------------
    st = pd.read_sql_query(
        "SELECT work_id, file, page, kind, sentence FROM statements "
        "WHERE work_id != ''", ft)
    st.to_sql("statements", out, index=False)
    ft.close()
    fm.close()

    rows = []
    for chapter, kind, ids in CHAPTERS:
        for i in ids:
            rows.append({"chapter": chapter, "anchor_kind": kind,
                         "anchor_id": i})
    pd.DataFrame(rows).to_sql("chapter_map", out, index=False)

    # --- search index -----------------------------------------------------
    out.executescript("""
    CREATE INDEX idx_w_comm ON works(community);
    CREATE INDEX idx_w_strand ON works(core_strand);
    CREATE INDEX idx_wa_w ON work_authors(work_id);
    CREATE INDEX idx_wa_a ON work_authors(author_id);
    CREATE INDEX idx_st_w ON statements(work_id);
    CREATE VIRTUAL TABLE works_fts USING fts5(
        work_id UNINDEXED, title, abstract, body,
        tokenize='porter unicode61');
    """)
    ft = sqlite3.connect(FT_DB)
    body = {wid: t for wid, t in ft.execute(
        "SELECT work_id, text FROM fulltext WHERE work_id != ''")}
    ft.close()
    cur = out.cursor()
    for r in works.itertuples():
        cur.execute("INSERT INTO works_fts VALUES (?,?,?,?)",
                    (r.work_id, r.title or "", r.abstract or "",
                     body.get(r.work_id, "")))
    out.commit()

    n_ft = int(works["has_fulltext"].sum())
    print("=== build_knowledgebase ===")
    print(f"  works       : {len(works):,} ({n_ft:,} with full text)")
    print(f"  authors     : {len(au):,}")
    print(f"  statements  : {len(st):,}")
    print(f"  chapters    : {len(CHAPTERS)}")
    print(f"  db          : {KB} ({KB.stat().st_size/1e9:.2f} GB)")
    out.close()


if __name__ == "__main__":
    main()
