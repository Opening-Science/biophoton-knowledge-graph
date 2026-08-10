"""Membership-strength metrics for the coupling clusters.

The Milestone-2 reports described each community by its *most-cited* work, and
that produced a list ("Hallmarks of Cancer", 66,806 cites) with no relation to
the cluster's subject. The reason is structural, not cosmetic:

  cited_by_count measures a work's standing in the world literature.
  Cluster membership is a property of the local coupling graph.

Inside community 0 the two are *inversely* related — works with >2000 citations
have a median coupling degree of 19, works with <25 citations a median of 85 —
because hyper-cited classics enter the universe as hop-2 forward-citation
neighbours whose own reference lists barely intersect the harvest. Ranking by
citations therefore selects the least representative members of a cluster.

This module computes the metrics that *are* properties of the local graph, so
a cluster can be described by works that actually hold it together:

  deg / strength   coupling degree and summed shared-reference weight
  intra_*          the part of that attachment landing inside the own cluster
  cohesion         intra_strength / strength — is the work really "in" here?
  seed_coupling    shared references with the seed set (field anchoring)
  topic_fit        overlap of the work's OpenAlex topics with the cluster's
  core_score       within-cluster percentile blend of the three above

Nothing here re-runs Leiden; it re-describes the partition that networks.py
already produced. Fixing the partition itself is a separate step (see
docs/CLUSTERING_STRATEGY.md).
"""
from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict

import pandas as pd

import config as C

MIN_COUPLING_WEIGHT = 2   # same threshold networks.py uses to keep an edge
SEED_COUPLE_MIN = 2       # shared refs before a work counts as "coupled to" a seed
PERIPHERY_DEG = 10        # degree at or below which a work is graph periphery

# core_score weights: structure, field anchoring, topical fit
W_STRUCTURE, W_ANCHOR, W_TOPIC = 0.45, 0.35, 0.20


# --------------------------------------------------------------------------- #
def load_frames(db_path=None):
    con = sqlite3.connect(str(db_path or C.DB_PATH))
    works = pd.read_sql_query(
        "SELECT work_id, doi, title, year, type, cited_by_count, is_oa, oa_url,"
        " is_seed, hop FROM works", con)
    edges = pd.read_sql_query(
        "SELECT src_work_id, dst_work_id FROM citation_edges", con)
    topics = pd.read_sql_query(
        "SELECT work_id, topic_name, field, score FROM topics", con)
    wa = pd.read_sql_query(
        "SELECT wa.work_id, wa.position, a.display_name, a.author_id "
        "FROM work_authors wa JOIN authors a ON a.author_id = wa.author_id", con)
    con.close()
    return works, edges, topics, wa


def coupling_index(edges: pd.DataFrame):
    """refs[w] = set of in-universe works w cites; citers[r] = set citing r."""
    refs = edges.groupby("src_work_id")["dst_work_id"].apply(set).to_dict()
    citers: dict[str, set] = defaultdict(set)
    for src, dsts in refs.items():
        for d in dsts:
            citers[d].add(src)
    return refs, citers


def neighbours(work_id: str, refs: dict, citers: dict) -> dict[str, int]:
    """Coupling neighbours of one work, weight = shared references, thresholded
    exactly as networks.build_coupling does."""
    counts: Counter = Counter()
    for d in refs.get(work_id, ()):
        for s in citers.get(d, ()):
            if s != work_id:
                counts[s] += 1
    return {k: v for k, v in counts.items() if v >= MIN_COUPLING_WEIGHT}


# --------------------------------------------------------------------------- #
def structural_metrics(work_ids, cluster_of: dict, refs, citers) -> pd.DataFrame:
    """Degree / strength, split into the part inside the work's own cluster."""
    rows = []
    for w in work_ids:
        nb = neighbours(w, refs, citers)
        own = cluster_of.get(w)
        intra = {k: v for k, v in nb.items() if cluster_of.get(k) == own}
        deg, strength = len(nb), sum(nb.values())
        rows.append({
            "work_id": w,
            "n_refs": len(refs.get(w, ())),
            "deg": deg,
            "strength": strength,
            "intra_deg": len(intra),
            "intra_strength": sum(intra.values()),
            "cohesion": round(sum(intra.values()) / strength, 4) if strength else 0.0,
        })
    return pd.DataFrame(rows)


def seed_metrics(work_ids, seed_ids, cluster_of: dict, refs) -> pd.DataFrame:
    """Shared-reference coupling to the seed set — the field-anchoring signal.

    Reported twice: against every seed, and against seeds sitting in the work's
    own cluster (the meaningful one for a cluster that is not the UPE core).
    """
    seed_refs = {s: refs.get(s, set()) for s in seed_ids}
    rows = []
    for w in work_ids:
        r = refs.get(w, set())
        own = cluster_of.get(w)
        tot = own_tot = n_any = n_own = 0
        for s, sr in seed_refs.items():
            if not r or not sr:
                continue
            shared = len(r & sr)
            if not shared:
                continue
            tot += shared
            if shared >= SEED_COUPLE_MIN:
                n_any += 1
            if cluster_of.get(s) == own:
                own_tot += shared
                if shared >= SEED_COUPLE_MIN:
                    n_own += 1
        rows.append({"work_id": w, "seed_coupling": tot, "n_seeds_coupled": n_any,
                     "seed_coupling_own": own_tot, "n_seeds_coupled_own": n_own})
    return pd.DataFrame(rows)


def topic_fit(work_topics: pd.DataFrame, cluster_of: dict, top_n=10) -> pd.DataFrame:
    """Share of a work's OpenAlex topics that are among its cluster's top-N."""
    wt = work_topics.copy()
    wt["cluster"] = wt["work_id"].map(cluster_of)
    wt = wt.dropna(subset=["cluster"])
    top_by_cluster = {
        cl: {t for t, _ in Counter(g["topic_name"]).most_common(top_n)}
        for cl, g in wt.groupby("cluster")}
    rows = []
    for w, g in wt.groupby("work_id"):
        top = top_by_cluster.get(g["cluster"].iloc[0], set())
        names = list(g["topic_name"])
        rows.append({"work_id": w,
                     "topic_fit": round(sum(n in top for n in names) / len(names), 3)
                                  if names else 0.0})
    return pd.DataFrame(rows)


def core_score(df: pd.DataFrame, cluster_col: str) -> pd.Series:
    """0-100 blend of within-cluster percentile ranks. Percentiles, not raw
    values, so a 500-work cluster and a 5000-work cluster stay comparable."""
    g = df.groupby(cluster_col)
    s = g["intra_strength"].rank(pct=True)
    a = g["n_seeds_coupled_own"].rank(pct=True)
    t = g["topic_fit"].rank(pct=True)
    return (100 * (W_STRUCTURE * s + W_ANCHOR * a + W_TOPIC * t)).round(1)
