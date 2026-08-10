"""Book-planning evidence tables from the knowledgebase.

Stage L. Turns knowledgebase.sqlite into the two data documents the book
synthesis is written from:

  outputs/book_planning/chapter_evidence.md
      per chapter: corpus depth (works / full text / OA / recency), the
      strongest works, and a ranked author shortlist whose activity is
      validated against the full text we actually hold -- not just citation
      counts. Includes a per-strand breakdown for the core chapter.

  outputs/book_planning/open_question_statements.md
      the mined open-problem sentences, filtered to the field proper,
      bucketed into themes, ranked, with exact provenance (author, year,
      page, DOI) so every claim in the final synthesis can cite a sentence
      a human can check.

This script computes; it does not editorialise. The judgment layer
(chapter_author_refinement.md, open_research_questions.md) is written from
these tables.
"""
from __future__ import annotations

import re
import sqlite3
from collections import defaultdict

import pandas as pd

import config as C

LIT = C.ROOT.parent / "literature"
KB = LIT / "knowledgebase.sqlite"
OUT = C.OUTPUTS / "book_planning"

ACTIVE_SINCE = 2019          # last in-universe work at/after this = active
RECENT = 2018

# Strand semantics from outputs/community0_subdivision.md (Leiden res 3.0
# inside coupling community 0). Ids are stable across reruns per
# MILESTONE2_DECISIONS.md.
STRANDS = {
    1:  "Human UPE & measurement methodology",
    9:  "Cell-to-cell communication through light",
    4:  "Delayed luminescence (Catania school)",
    2:  "Plant & seed UPE (Popp school lineage)",
    0:  "Analytical chemiluminescence & PDT (historical)",
    15: "Neural & brain optical signalling",
    19: "Coherence theory (Popp school)",
    5:  "Water & coherent domains",
    18: "Retinal & single-photon visual signalling",
    8:  "Consciousness-adjacent (Persinger school)",
    7:  "Quantum consciousness (Hameroff/Penrose)",
    3:  "Frohlich condensation & EM field theory",
    10: "Microtubule electrodynamics",
    6:  "Quantum biology & photosynthesis (mainstream)",
    11: "EM bioeffects & microbial",
}

# chapter -> anchors into the map. Mirrors book_chapter_recommendation.md.
CHAPTERS = [
    ("Ch 1  What UPE is (definitions, mechanisms, measurement)",
     dict(strands=[1])),
    ("Ch 2  Where the field ends (boundary: sonoluminescence adjacency)",
     dict(communities=[1, 2, 4, 6])),
    ("Ch 4  Inside the core (nine strands)",
     dict(communities=[0])),
    ("Ch 5  The reactive-oxygen connection",
     dict(communities=[3])),
    ("Ch 6  The consciousness-adjacent fringe",
     dict(strands=[8, 7])),
]

# Per-chapter vocabulary for full-text validation: an author only counts as
# textually grounded for a chapter if the papers we hold from them actually
# use its vocabulary.
CHAPTER_TERMS = {
    "Ch 1": ["ultra-weak photon emission", "ultraweak photon emission",
             "biophoton", "photomultiplier", "photon counting",
             "spectral", "dark count", "detector"],
    "Ch 2": ["sonoluminescence", "cavitation", "bubble collapse",
             "acoustic"],
    "Ch 4": ["biophoton", "ultraweak", "ultra-weak", "delayed luminescence",
             "photon emission"],
    "Ch 5": ["reactive oxygen", "singlet oxygen", "lipid peroxidation",
             "chemiluminescence", "triplet carbonyl", "oxidative stress"],
    "Ch 6": ["consciousness", "biofield", "electroencephalog",
             "geomagnetic", "psi ", "telepath"],
}

# Theme buckets for the open-question synthesis. A statement lands in the
# first theme whose pattern hits; order encodes priority.
THEMES = [
    ("Mechanism & molecular sources",
     r"mechanism|source of|origin of|singlet oxygen|triplet|carbonyl|"
     r"excited species|ros generat|radical"),
    ("Coherence, statistics & quantum claims",
     r"coheren|squeezed|photocount|poisson|quantum (?:state|nature|origin|"
     r"propert)|entangle|nonclassical|non-classical"),
    ("Measurement, calibration & standardisation",
     r"calibrat|standardi[sz]|traceab|detection limit|dark[- ]count|"
     r"signal-to-noise|quantum efficiency|(?:ir)?reproducib|replicat|"
     r"inter-?laborator|measurement uncertaint|detector|photomultiplier|"
     r"photon[- ]?counting|absolute (?:calibration|photon|radiometr|"
     r"quantification)"),
    ("Biological function & signalling",
     r"signal(?:ling|ing)|communicat|function(?:al)? (?:role|significance)|"
     r"biological (?:role|function|significance)|information transfer"),
    ("Neural & brain UPE",
     r"neuron|brain|neural|axon|cogniti|extracranial"),
    ("Clinical & diagnostic applications",
     r"clinical|diagnos|cancer|tumou?r|disease|patient|therap|oxidative "
     r"stress marker"),
    ("Imaging & instrumentation frontiers",
     r"imaging|camera|ccd|cmos|spad|emccd|in vivo|spatial resolution"),
]

FIRST_AUTHOR_RE = re.compile(r"^([^;,]+)")

# A mined sentence only enters the synthesis when it, or the title of the work
# it came from, is recognisably about the field. The seed neighbourhood (hop 1)
# contains methods papers from quantum optics, colloid physics, sports
# medicine... whose open problems are real but not ours.
UPE_VOCAB = re.compile(
    r"biophoton|ultra-?weak photon|photon emission|\bUPE\b|photocount|"
    r"delayed luminescence|autoluminescence|"
    r"(?:bio|chemi|electrochemi)?luminescen|singlet oxygen|"
    r"reactive oxygen|oxidative|photomultiplier|single-photon|"
    r"photon[- ]counting|sonoluminescen", re.I)


def load(con, sql, **kw):
    return pd.read_sql_query(sql, con, **kw)


def anchor_mask(w: pd.DataFrame, anch: dict) -> pd.Series:
    m = pd.Series(False, index=w.index)
    for c in anch.get("communities", []):
        m |= w["community"] == c
    for s in anch.get("strands", []):
        m |= w["core_strand"] == s
    return m


def author_table(con, w: pd.DataFrame, wids: pd.Series,
                 terms: list[str]) -> pd.DataFrame:
    """Ranked author candidates for one anchor set."""
    ids = ",".join(f"'{x}'" for x in wids)
    wa = load(con, f"SELECT work_id, author_id, is_corresponding "
                   f"FROM work_authors WHERE work_id IN ({ids})")
    au = load(con, "SELECT author_id, display_name, orcid, institution, "
                   "country, openness_score, last_year, first_year "
                   "FROM authors")
    sub = w[w["work_id"].isin(set(wids))][
        ["work_id", "year", "paper_rank_score", "has_fulltext",
         "cited_by_count"]]
    j = wa.merge(sub, on="work_id").merge(au, on="author_id")

    g = j.groupby(["author_id", "display_name"]).agg(
        n_anchor=("work_id", "nunique"),
        n_recent=("year", lambda y: int((y >= RECENT).sum())),
        n_fulltext=("has_fulltext", "sum"),
        n_corresp=("is_corresponding", "sum"),
        rank_mass=("paper_rank_score", "sum"),
        cites=("cited_by_count", "sum"),
        orcid=("orcid", "first"),
        institution=("institution", "first"),
        country=("country", "first"),
        openness=("openness_score", "first"),
        last_year=("last_year", "first"),
    ).reset_index()

    # textual grounding: term hits in the full text we hold for their works
    ft_wids = set(sub[sub["has_fulltext"] == 1]["work_id"])
    hits = defaultdict(int)
    if terms and ft_wids:
        ftcon = sqlite3.connect(LIT / "fulltext.sqlite")
        by_author = j[j["work_id"].isin(ft_wids)].groupby(
            "author_id")["work_id"].apply(set)
        texts = {}
        for wid in ft_wids:
            row = ftcon.execute(
                "SELECT lower(text) FROM fulltext WHERE work_id=? "
                "ORDER BY n_chars DESC LIMIT 1", (wid,)).fetchone()
            texts[wid] = row[0] if row else ""
        ftcon.close()
        tl = [t.lower() for t in terms]
        wid_hits = {wid: sum(txt.count(t) for t in tl)
                    for wid, txt in texts.items()}
        for aid, ws in by_author.items():
            hits[aid] = sum(wid_hits.get(x, 0) for x in ws)
    g["term_hits"] = g["author_id"].map(hits).fillna(0).astype(int)

    g["active"] = (g["last_year"] >= ACTIVE_SINCE)
    g["score"] = (g["n_anchor"].clip(upper=30) * 1.0
                  + g["n_recent"] * 2.0
                  + g["n_corresp"] * 0.5
                  + g["rank_mass"] * 3.0
                  + g["openness"].fillna(0) * 3.0
                  + (g["term_hits"] > 20) * 2.0
                  + g["active"] * 4.0)
    return g.sort_values("score", ascending=False)


def fmt_authors(g: pd.DataFrame, n: int = 14) -> list[str]:
    L = ["| Author | Works | Recent | Held FT | Term hits | Corresp | "
         "Open | Active to | ORCID | Institution |",
         "|---|---:|---:|---:|---:|---:|---:|---|---|---|"]
    for r in g.head(n).itertuples():
        orcid = (r.orcid if isinstance(r.orcid, str) else "").replace(
            "https://orcid.org/", "")
        inst = (r.institution if isinstance(r.institution, str) else "")[:34]
        op = f"{r.openness:.2f}" if pd.notna(r.openness) else "-"
        ly = int(r.last_year) if pd.notna(r.last_year) else "-"
        L.append(f"| {r.display_name} | {r.n_anchor} | {r.n_recent} | "
                 f"{int(r.n_fulltext)} | {r.term_hits} | "
                 f"{int(r.n_corresp)} | {op} | {ly} | {orcid} | {inst} |")
    return L


def top_works(w: pd.DataFrame, mask: pd.Series, n: int = 8) -> list[str]:
    L = []
    sub = w[mask].sort_values("paper_rank_score", ascending=False).head(n)
    for r in sub.itertuples():
        fa = FIRST_AUTHOR_RE.match(r.authors or "")
        fa = fa.group(1).strip() if fa else "?"
        yr = int(r.year) if pd.notna(r.year) else "n.d."
        ft = "FT" if r.has_fulltext else ("OA" if r.is_oa else "closed")
        L.append(f"- {fa} ({yr}): {(r.title or '')[:100]} "
                 f"[{ft}] `{r.work_id}`")
    return L


def chapter_evidence(con, w: pd.DataFrame) -> None:
    L = ["# Chapter evidence base\n",
         "Corpus depth and author candidates per chapter, computed from "
         "the knowledgebase (works + full text + clustering + openness). "
         "`Held FT` = works by that author in the chapter anchor that we "
         "hold as extracted full text. `Term hits` = occurrences of the "
         "chapter's core vocabulary in those held texts -- textual "
         "grounding, not just co-citation.\n"]
    for title, anch in CHAPTERS:
        mask = anchor_mask(w, anch)
        sub = w[mask]
        key = title.split()[0] + " " + title.split()[1]
        terms = CHAPTER_TERMS.get(key, [])
        n = len(sub)
        nft = int(sub["has_fulltext"].sum())
        noa = int(sub["is_oa"].sum())
        med = int(sub["year"].median()) if n else 0
        rec = int((sub["year"] >= RECENT).sum())
        L.append(f"## {title}\n")
        L.append(f"- **{n:,} works** in anchor; {noa:,} OA ({noa/max(n,1):.0%}); "
                 f"**{nft:,} held as full text** ({nft/max(n,1):.0%}); "
                 f"median year {med}; {rec:,} works from {RECENT} on.\n")
        L.append("**Strongest works (paper rank):**\n")
        L.extend(top_works(w, mask))
        L.append("\n**Author candidates (composite of anchor output, "
                 "recency, rank mass, openness, activity):**\n")
        g = author_table(con, w, sub["work_id"], terms)
        L.extend(fmt_authors(g))
        L.append("")

    # per-strand mini-tables for the core chapter
    L.append("## Core strands (chapter 4 internal structure)\n")
    for sid, label in STRANDS.items():
        sub = w[w["core_strand"] == sid]
        if not len(sub):
            continue
        nft = int(sub["has_fulltext"].sum())
        med = int(sub["year"].median())
        L.append(f"### Strand {sid}: {label}\n")
        L.append(f"- {len(sub)} works, {nft} full text, median {med}\n")
        g = author_table(con, w, sub["work_id"], [])
        L.extend(fmt_authors(g, n=6))
        L.append("")

    (OUT / "chapter_evidence.md").write_text("\n".join(L))
    print(f"  wrote {OUT/'chapter_evidence.md'}")


KIND_PRIORITY = {"open_question": 0, "controversy": 1, "measurement_gap": 2,
                 "future_work": 3, "limitation": 4}


def statement_tables(con, w: pd.DataFrame) -> None:
    st = load(con, "SELECT * FROM statements")
    meta = w.set_index("work_id")
    st = st[st["work_id"].isin(meta.index)]
    # field proper: the UPE core, the ROS wing, the seed neighbourhood, and
    # everything we curated by hand
    keep = meta["community"].isin([0, 3]) | (meta["hop"] <= 1) | \
        (meta["is_seed"] == 1)
    st = st[st["work_id"].map(keep)]
    st = st.join(meta[["title", "authors", "year", "doi",
                       "paper_rank_score", "community", "core_strand"]],
                 on="work_id")
    # a work held twice (harvested copy + curated preprint) yields the same
    # sentence twice
    st["skey"] = (st["sentence"].str.lower()
                  .str.replace(r"[^a-z0-9]+", "", regex=True).str[:120])
    st = st.drop_duplicates(["work_id", "skey"])
    on_topic = (st["sentence"].str.contains(UPE_VOCAB) |
                st["title"].fillna("").str.contains(UPE_VOCAB))
    print(f"  statements: {len(st)} in field scope, "
          f"{int(on_topic.sum())} on topic")
    st = st[on_topic]
    st["kp"] = st["kind"].map(KIND_PRIORITY)
    st = st.sort_values(["kp", "paper_rank_score"],
                        ascending=[True, False])
    # each statement goes to its first matching theme (THEMES order is
    # priority), and a work contributes at most two statements per theme so
    # one chatty review cannot flood a bucket
    themed: dict[str, list] = {t: [] for t, _ in THEMES}
    compiled = [(t, re.compile(p, re.I)) for t, p in THEMES]
    per_work_theme: dict[tuple[str, str], int] = defaultdict(int)
    for r in st.itertuples():
        for theme, rx in compiled:
            if rx.search(r.sentence):
                if per_work_theme[(r.work_id, theme)] < 2:
                    themed[theme].append(r)
                    per_work_theme[(r.work_id, theme)] += 1
                break
    themed = {t: pd.DataFrame(rows) for t, rows in themed.items()}

    L = ["# Mined open-problem statements, by theme\n",
         "Sentences extracted verbatim from the full-text corpus (with page "
         "provenance), restricted to the UPE core, the ROS wing, and the "
         "seed neighbourhood. Ranked by statement kind "
         "(open_question > controversy > measurement_gap > future_work > "
         "limitation) then paper rank. Max one statement per work per "
         "theme.\n"]
    for theme, pat in THEMES:
        df = themed[theme]
        L.append(f"## {theme}  ({len(df)} statements)\n")
        for r in (df.head(14).itertuples() if len(df) else []):
            fa = FIRST_AUTHOR_RE.match(r.authors or "")
            fa = fa.group(1).strip() if fa else "?"
            yr = int(r.year) if pd.notna(r.year) else "n.d."
            doi = f" doi:{r.doi}" if r.doi else ""
            L.append(f"- \"{r.sentence.strip()}\"  ")
            L.append(f"  -- {fa} ({yr}), p.{r.page}, [{r.kind}] "
                     f"`{r.work_id}`{doi}")
        L.append("")
    n_total = sum(len(v) for v in themed.values())
    L.append(f"_{n_total} themed statements from "
             f"{st['work_id'].nunique()} works._")
    (OUT / "open_question_statements.md").write_text("\n".join(L))
    print(f"  wrote {OUT/'open_question_statements.md'} "
          f"({n_total} statements)")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(KB)
    w = load(con, "SELECT * FROM works")
    chapter_evidence(con, w)
    statement_tables(con, w)
    con.close()


if __name__ == "__main__":
    main()
