"""Subdivide coupling community 0 at higher Leiden resolution.

Community 0 (the broad "biophoton core") bundles the true UPE core with the
biofield/EEG/quantum-biology literature pulled in by coupling. We induce the
coupling subgraph on just community-0 works and re-cluster at a higher
resolution to separate those strands, then report where the Cifra/Popp/Van
Wijk/Kobayashi seeds concentrate (= the true UPE core sub-cluster).

Writes outputs/community0_subdivision.md and
data/exports/community0_subclusters.csv.
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter

import igraph as ig
import leidenalg as la
import pandas as pd

import config as C

SUBDIVIDE_RESOLUTION = 3.0
CITATION_MAGNET = 8000
CORE_NAMES = ("cifra", "popp", "van wijk", "wijk", "kobayashi", "pospisil",
              "pospíšil", "scholkmann", "salari", "musumeci", "scordino",
              "prasad", "ignatov")


def main() -> None:
    con = sqlite3.connect(C.DB_PATH)
    wc = pd.read_csv(C.EXPORTS / "work_communities.csv")
    comm0 = set(wc[wc["coupling_community"] == 0]["work_id"])
    print(f"Community 0: {len(comm0)} works")

    g = ig.Graph.Read_GraphML(str(C.EXPORTS / "coupling.graphml"))
    keep = [v.index for v in g.vs if v["name"] in comm0]
    sub = g.induced_subgraph(keep)
    print(f"Induced coupling subgraph: {sub.vcount()} nodes, "
          f"{sub.ecount()} edges")

    part = la.find_partition(
        sub, la.RBConfigurationVertexPartition,
        weights="weight" if "weight" in sub.es.attributes() else None,
        resolution_parameter=SUBDIVIDE_RESOLUTION, seed=42)
    sub.vs["subcluster"] = part.membership
    n_sub = len(set(part.membership))
    print(f"Leiden @res={SUBDIVIDE_RESOLUTION}: {n_sub} sub-clusters")

    subassign = pd.DataFrame({
        "work_id": sub.vs["name"], "subcluster": sub.vs["subcluster"]})
    subassign.to_csv(C.EXPORTS / "community0_subclusters.csv", index=False)

    # metadata for labeling
    works = pd.read_sql_query(
        "SELECT work_id, title, year, cited_by_count, is_seed FROM works", con)
    works = works.merge(subassign, on="work_id", how="inner")
    topics = pd.read_sql_query(
        "SELECT work_id, topic_name, score FROM topics", con)
    top_topic = topics.sort_values("score", ascending=False).drop_duplicates(
        "work_id")
    wa = pd.read_sql_query(
        "SELECT wa.work_id, a.display_name FROM work_authors wa "
        "JOIN authors a ON a.author_id=wa.author_id", con)
    # forward seed-anchor: seeds + works citing a seed
    seeds = set(works[works["is_seed"] == 1]["work_id"])
    edges = pd.read_sql_query(
        "SELECT src_work_id, dst_work_id FROM citation_edges", con)
    all_seeds = set(pd.read_sql_query(
        "SELECT work_id FROM works WHERE is_seed=1", con)["work_id"])
    citing_seed = set(edges[edges["dst_work_id"].isin(all_seeds)]["src_work_id"])
    anchor = seeds | citing_seed

    rows = []
    for sc, grp in works.groupby("subcluster"):
        ids = set(grp["work_id"])
        anchor_ids = ids & anchor or ids
        tp = top_topic[top_topic["work_id"].isin(ids)]["topic_name"]
        au = wa[wa["work_id"].isin(anchor_ids)]["display_name"].dropna()
        core_hits = sum(1 for a in au for n in [a.lower()]
                        if any(cn in n for cn in CORE_NAMES))
        reps = (grp[(grp["work_id"].isin(anchor)) &
                    (grp["cited_by_count"] < CITATION_MAGNET)]
                .sort_values("cited_by_count", ascending=False).head(3))
        if reps.empty:
            reps = grp.sort_values("cited_by_count", ascending=False).head(3)
        rows.append({
            "subcluster": int(sc),
            "n_works": len(grp),
            "n_seeds": int((grp["is_seed"] == 1).sum()),
            "core_author_mentions": core_hits,
            "median_year": int(grp["year"].dropna().median())
                           if grp["year"].notna().any() else None,
            "top_topics": [t for t, _ in Counter(tp).most_common(4)],
            "top_authors": [a for a, _ in Counter(au).most_common(6)],
            "reps": [f"{str(r.title)[:80]} ({r.year}, {r.cited_by_count}c)"
                     for r in reps.itertuples()],
        })
    rows.sort(key=lambda r: (r["n_seeds"], r["core_author_mentions"]),
              reverse=True)

    # classify each sub-cluster: core UPE strand vs fringe, and flag the
    # consciousness/paranormal one specifically (topics or Persinger-wing authors)
    CONSC_AUTHORS = ("persinger", "dotta", "murugan", "rouleau", "saroka",
                     "karbowski")
    for r in rows:
        top2_topics = " ".join(r["top_topics"][:2]).lower()
        top3_authors = " ".join(r["top_authors"][:3]).lower()
        r["is_consciousness"] = (
            "paranormal" in top2_topics or
            any(a in top3_authors for a in CONSC_AUTHORS))
        # a core UPE strand: carries seeds and isn't the consciousness wing
        r["is_core"] = (r["n_seeds"] >= 3) and (not r["is_consciousness"])
        r["label"] = "; ".join(r["top_topics"][:2]) if r["top_topics"] else \
            f"sub-cluster {r['subcluster']}"
    labels = {r["subcluster"]: {
        "label": r["label"], "n_works": r["n_works"], "n_seeds": r["n_seeds"],
        "is_core": r["is_core"], "is_consciousness": r["is_consciousness"],
        "core_author_mentions": r["core_author_mentions"],
        "median_year": r["median_year"],
        "top_authors": r["top_authors"], "top_topics": r["top_topics"],
        "reps": r["reps"]} for r in rows}
    (C.EXPORTS / "community0_subcluster_labels.json").write_text(
        json.dumps(labels, indent=2))

    # report
    L = ["# Community 0 subdivision — separating the UPE core\n"]
    L.append(f"_Induced coupling subgraph of the {len(comm0)} community-0 works, "
             f"re-clustered with Leiden at resolution {SUBDIVIDE_RESOLUTION} "
             f"→ {n_sub} sub-clusters. Sorted by seed concentration._\n")
    L.append("The true biophoton/UPE core is the sub-cluster where the seeds "
             "and core authors (Cifra, Popp, Van Wijk, Kobayashi, Pospíšil, "
             "Musumeci, Scordino) concentrate; the biofield/EEG/quantum-biology "
             "strands split into their own sub-clusters.\n")
    for r in rows:
        if r["n_works"] < 15 and r["n_seeds"] == 0:
            continue
        tag = ""
        if r["n_seeds"] >= 10 or r["core_author_mentions"] >= 5:
            tag = "  ← **UPE core strand**"
        L.append(f"## Sub-cluster {r['subcluster']} — {r['n_works']} works, "
                 f"{r['n_seeds']} seeds, median {r['median_year']}{tag}")
        L.append(f"- **Topics:** {', '.join(r['top_topics'])}")
        L.append(f"- **Authors:** {', '.join(r['top_authors'])}")
        for rp in r["reps"]:
            L.append(f"- _rep:_ {rp}")
        L.append("")
    out = C.OUTPUTS / "community0_subdivision.md"
    out.write_text("\n".join(L))
    print(f"Wrote {out}")

    print("\n=== summary (sub-clusters with seeds) ===")
    for r in rows:
        if r["n_seeds"] > 0:
            print(f"  sub {r['subcluster']:>2}: {r['n_works']:>4} works, "
                  f"{r['n_seeds']:>3} seeds, {r['core_author_mentions']:>3} "
                  f"core-mentions | {', '.join(r['top_topics'][:2])}")
    con.close()


if __name__ == "__main__":
    main()
