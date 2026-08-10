"""Build outputs/cluster_explorer.html — browse the works behind every cluster.

One self-contained page (no CDN, no server) holding every work in the coupling
universe with its cluster assignment and its membership-strength metrics from
cluster_metrics.py. The point is to make the partition auditable by hand: pick a
cluster, sort it three ways, and see which works actually hold it together
versus which ones merely have large citation counts.

Two levels of cluster are exposed:
  * the 11 bibliographic-coupling communities from networks.py (resolution 1.0)
  * the 37 sub-clusters of community 0 from subdivide.py (resolution 3.0)
plus an explicit "unassigned" bucket for universe works that never entered the
coupling graph, so the work counts add up to the whole harvest.

    python src/build_cluster_explorer.py
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter

import pandas as pd

import cluster_metrics as M
import config as C

OUT = C.OUTPUTS / "cluster_explorer.html"
V2_CSV = C.EXPORTS / "work_communities_v2.csv"
SNAPSHOT = "OpenAlex harvest 2026-07-19/20"

MAX_AUTHORS = 5          # authors kept per work for the table
TOP_TERMS = 14           # distinctive terms per cluster
MIN_V2_SIZE = 20         # v2 clusters below this are pooled into one bucket
STOP = set("""
a an and are as at be by for from has have in into is it its of on or that the
to was were with we our their this these those study studies research effect
effects role using use used based new novel analysis review between during via
after before under over more most non high low can may towards toward its i ii
iii two three first second human cell cells system systems method methods
application applications approach model models potential evidence
""".split())


# --------------------------------------------------------------------------- #
def distinctive_terms(titles: pd.Series, corpus_freq: Counter, corpus_n: int,
                      k: int = TOP_TERMS) -> list[str]:
    """Terms over-represented in a cluster's titles relative to the whole
    universe. Weighted log-odds, so a term needs both lift and volume."""
    local: Counter = Counter()
    n = 0
    for t in titles.dropna():
        toks = {w for w in re.findall(r"[a-z][a-z\-]{2,}", str(t).lower())
                if w not in STOP}
        local.update(toks)
        n += 1
    if not n:
        return []
    scored = []
    for term, cnt in local.items():
        if cnt < 3:
            continue
        p_local = cnt / n
        p_corpus = max(corpus_freq.get(term, 0), 1) / corpus_n
        scored.append((p_local * math.log(p_local / p_corpus), term))
    scored.sort(reverse=True)
    return [t for _, t in scored[:k]]


def corpus_term_freq(titles: pd.Series) -> tuple[Counter, int]:
    freq: Counter = Counter()
    n = 0
    for t in titles.dropna():
        freq.update({w for w in re.findall(r"[a-z][a-z\-]{2,}", str(t).lower())
                     if w not in STOP})
        n += 1
    return freq, n


# --------------------------------------------------------------------------- #
def build_payload() -> dict:
    works, edges, topics, wa = M.load_frames()
    wc = pd.read_csv(C.EXPORTS / "work_communities.csv")[
        ["work_id", "coupling_community"]]
    sub = pd.read_csv(C.EXPORTS / "community0_subclusters.csv")

    df = works.merge(wc, on="work_id", how="left").merge(sub, on="work_id",
                                                         how="left")
    df["cluster"] = df["coupling_community"].apply(
        lambda v: f"c{int(v)}" if pd.notna(v) else "unassigned")
    df["subcluster"] = df["subcluster"].apply(
        lambda v: f"c0.s{int(v)}" if pd.notna(v) else None)

    if V2_CSV.exists():
        v2 = pd.read_csv(V2_CSV)[["work_id", "community_v2", "stability"]]
        df = df.merge(v2, on="work_id", how="left")
        counts = df["community_v2"].value_counts()
        big = set(counts[counts >= MIN_V2_SIZE].index)
        df["v2"] = df["community_v2"].apply(
            lambda v: None if pd.isna(v) else
            (f"v{int(v)}" if v in big else "v.small"))
    else:
        df["v2"], df["stability"] = None, None

    cluster_of = dict(zip(df["work_id"], df["cluster"]))
    subcluster_of = {w: s for w, s in zip(df["work_id"], df["subcluster"]) if s}
    v2_of = {w: v for w, v in zip(df["work_id"], df["v2"]) if isinstance(v, str)}

    print("indexing coupling graph...")
    refs, citers = M.coupling_index(edges)
    ids = list(df["work_id"])
    seed_ids = list(df.loc[df["is_seed"] == 1, "work_id"])

    print(f"structural metrics for {len(ids)} works...")
    df = df.merge(M.structural_metrics(ids, cluster_of, refs, citers),
                  on="work_id", how="left")
    print(f"seed anchoring against {len(seed_ids)} seeds...")
    df = df.merge(M.seed_metrics(ids, seed_ids, cluster_of, refs),
                  on="work_id", how="left")
    df = df.merge(M.topic_fit(topics[["work_id", "topic_name"]], cluster_of),
                  on="work_id", how="left")
    df[["deg", "strength", "intra_deg", "intra_strength", "n_refs",
        "seed_coupling", "n_seeds_coupled", "seed_coupling_own",
        "n_seeds_coupled_own"]] = df[
        ["deg", "strength", "intra_deg", "intra_strength", "n_refs",
         "seed_coupling", "n_seeds_coupled", "seed_coupling_own",
         "n_seeds_coupled_own"]].fillna(0).astype(int)
    df[["cohesion", "topic_fit"]] = df[["cohesion", "topic_fit"]].fillna(0.0)

    df["core_c"] = M.core_score(df, "cluster")

    def level_score(members: pd.DataFrame, col: str, assign: dict, out: str):
        """core_score recomputed against a different partition of the same works."""
        if not len(members):
            df[out] = None
            return
        ids_ = list(members["work_id"])
        st = M.structural_metrics(ids_, assign, refs, citers)
        sd = M.seed_metrics(ids_, list(members.loc[members["is_seed"] == 1,
                                                   "work_id"]), assign, refs)
        s = (members[["work_id", col, "topic_fit"]]
             .merge(st[["work_id", "intra_strength"]], on="work_id")
             .merge(sd[["work_id", "n_seeds_coupled_own"]], on="work_id"))
        s[out] = M.core_score(s, col)
        df[out] = df["work_id"].map(dict(zip(s["work_id"], s[out])))

    level_score(df[df["subcluster"].notna()].copy(), "subcluster",
                subcluster_of, "core_s")
    level_score(df[df["v2"].notna()].copy(), "v2", v2_of, "core_v")

    # ---- lookup tables ---------------------------------------------------
    wa = wa.sort_values("position")
    au_by_work = wa.groupby("work_id")["display_name"].apply(
        lambda s: list(dict.fromkeys(s))[:MAX_AUTHORS]).to_dict()
    tp = topics.sort_values("score", ascending=False)
    tp_by_work = tp.groupby("work_id")["topic_name"].apply(
        lambda s: list(dict.fromkeys(s))[:3]).to_dict()

    author_names, author_idx = [], {}
    topic_names, topic_idx = [], {}

    def aidx(n):
        if n not in author_idx:
            author_idx[n] = len(author_names)
            author_names.append(n)
        return author_idx[n]

    def tidx(n):
        if n not in topic_idx:
            topic_idx[n] = len(topic_names)
            topic_names.append(n)
        return topic_idx[n]

    cluster_names, cidx = [], {}

    def clidx(n):
        if n not in cidx:
            cidx[n] = len(cluster_names)
            cluster_names.append(n)
        return cidx[n]

    rows = []
    for r in df.itertuples():
        doi = (r.doi or "").replace("https://doi.org/", "") if isinstance(r.doi, str) else ""
        rows.append([
            str(r.work_id).lstrip("W"),
            (str(r.title) if isinstance(r.title, str) else ""),
            int(r.year) if pd.notna(r.year) else 0,
            int(r.cited_by_count or 0),
            int(r.is_seed or 0),
            int(r.hop) if pd.notna(r.hop) else -1,
            r.deg, r.strength, r.intra_deg, r.intra_strength,
            round(float(r.cohesion), 3),
            r.seed_coupling, r.n_seeds_coupled_own,
            round(float(r.topic_fit), 3),
            float(r.core_c) if pd.notna(r.core_c) else 0.0,
            float(r.core_s) if pd.notna(r.core_s) else -1.0,
            clidx(r.cluster),
            clidx(r.subcluster) if isinstance(r.subcluster, str) else -1,
            doi,
            int(r.is_oa or 0),
            [aidx(a) for a in au_by_work.get(r.work_id, [])],
            [tidx(t) for t in tp_by_work.get(r.work_id, [])],
            float(r.core_v) if pd.notna(r.core_v) else -1.0,
            clidx(r.v2) if isinstance(r.v2, str) else -1,
            round(float(r.stability), 3) if pd.notna(r.stability) else -1.0,
        ])

    # ---- cluster summaries ----------------------------------------------
    corpus_freq, corpus_n = corpus_term_freq(df["title"])
    top_topic = tp.drop_duplicates("work_id").set_index("work_id")["topic_name"]
    clusters = []

    def summarize(cid: str, parent, level: int, g: pd.DataFrame,
                  partition: str = "v1"):
        ids_ = set(g["work_id"])
        au = [a for w in ids_ for a in au_by_work.get(w, [])]
        tps = [top_topic.get(w) for w in ids_ if top_topic.get(w)]
        magnets = g.nlargest(3, "cited_by_count")
        stab = g["stability"].dropna()
        return {
            "id": cid, "parent": parent, "level": level,
            "partition": partition,
            "stability": round(float(stab.mean()), 3) if len(stab) else None,
            "n": int(len(g)),
            "seeds": int((g["is_seed"] == 1).sum()),
            "hops": {str(k): int(v) for k, v in
                     Counter(g["hop"].dropna().astype(int)).items()},
            "medyear": int(g["year"].dropna().median()) if g["year"].notna().any() else None,
            "med_deg": int(g["deg"].median()),
            "periphery": int((g["deg"] <= M.PERIPHERY_DEG).sum()),
            "med_cites": int(g["cited_by_count"].median()),
            "terms": distinctive_terms(g["title"], corpus_freq, corpus_n),
            "topics": [t for t, _ in Counter(tps).most_common(6)],
            "authors": [a for a, _ in Counter(au).most_common(8)],
            "magnet_gap": [
                {"title": str(m.title)[:90], "cites": int(m.cited_by_count),
                 "deg": int(m.deg), "core": float(m.core_c) if pd.notna(m.core_c) else 0.0}
                for m in magnets.itertuples()],
        }

    for cl, g in df.groupby("cluster"):
        clusters.append(summarize(cl, None, 0, g))
    for sc, g in df[df["subcluster"].notna()].groupby("subcluster"):
        clusters.append(summarize(sc, "c0", 1, g))
    for v, g in df[df["v2"].notna()].groupby("v2"):
        clusters.append(summarize(v, None, 0, g, partition="v2"))
    clusters.sort(key=lambda c: (c["parent"] or "", -c["n"]))

    return {
        "meta": {
            "snapshot": SNAPSHOT,
            "n_works": int(len(df)),
            "n_in_graph": int((df["cluster"] != "unassigned").sum()),
            "n_seeds": int((df["is_seed"] == 1).sum()),
            "n_clusters": int(df["cluster"].nunique()),
            "periphery_deg": M.PERIPHERY_DEG,
            "weights": {"structure": M.W_STRUCTURE, "anchor": M.W_ANCHOR,
                        "topic": M.W_TOPIC},
            "v2": (json.loads((C.EXPORTS / "recluster_report.json").read_text())
                   if (C.EXPORTS / "recluster_report.json").exists() else None),
            "min_v2_size": MIN_V2_SIZE,
        },
        "clusterNames": cluster_names,
        "authorNames": author_names,
        "topicNames": topic_names,
        "clusters": clusters,
        "works": rows,
    }


# --------------------------------------------------------------------------- #
def render(payload: dict) -> str:
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    tpl = (C.SRC_DIR / "cluster_explorer_template.html").read_text(encoding="utf-8")
    return tpl.replace("/*__PAYLOAD__*/null", data)


def main() -> None:
    payload = build_payload()
    html = render(payload)
    OUT.write_text(html, encoding="utf-8")
    mb = len(html.encode()) / 1e6
    print(f"\nWrote {OUT}  ({mb:.1f} MB, {payload['meta']['n_works']} works, "
          f"{len(payload['clusters'])} clusters)")


if __name__ == "__main__":
    main()
