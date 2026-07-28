"""Stage G — composite outreach ranking (spec §8).

Per canonical researcher, normalize each term to [0,1] across the scored set:

  0.30 seed_connectedness  (authored seed works + works cited by seeds)
  0.20 field_centrality    (eigenvector centrality, coauthorship graph)
  0.20 recent_activity     (in-universe works in the last 5 years)
  0.15 topical_fit         (share of in-universe works on core biophoton topics)
  0.15 openness_score      (Stage E)

Scope: researchers with >=1 work in the in-scope coupling communities
(0 core, 3 ROS/redox, 1/2/4/6 sonoluminescence-cavitation). Emits
researchers.csv plus filtered views. Joins contacts if contacts.py has run.
"""
from __future__ import annotations

import json
import sqlite3

import numpy as np
import pandas as pd

import config as C
from author_merge import build_canonical_map

SCOPE_COMMUNITIES = {0, 1, 2, 3, 4, 6}
RECENT_YEAR = 2021  # last 5y relative to the 2026 snapshot


def norm01(s: pd.Series, log: bool = False) -> pd.Series:
    x = np.log1p(s.astype(float)) if log else s.astype(float)
    lo, hi = x.min(), x.max()
    if hi <= lo:
        return pd.Series(0.0, index=s.index)
    return (x - lo) / (hi - lo)


def community_label(labels: list[dict]) -> dict[int, str]:
    out = {}
    for c in labels:
        topics = c.get("top_topics") or []
        out[c["community"]] = "; ".join(topics[:2]) if topics else f"community {c['community']}"
    return out


def main() -> None:
    con = sqlite3.connect(C.DB_PATH)
    canon = build_canonical_map(con)

    works = pd.read_sql_query(
        "SELECT work_id, year, cited_by_count, is_seed FROM works", con)
    wc = pd.read_csv(C.EXPORTS / "work_communities.csv")[
        ["work_id", "coupling_community"]]
    works = works.merge(wc, on="work_id", how="left")
    wa = pd.read_sql_query("SELECT work_id, author_id FROM work_authors", con)
    wa["canon"] = wa["author_id"].map(canon).fillna(wa["author_id"])

    # --- seed connectedness ---------------------------------------------
    seed_ids = set(works[works["is_seed"] == 1]["work_id"])
    edges = pd.read_sql_query(
        "SELECT src_work_id, dst_work_id FROM citation_edges", con)
    # works cited BY a seed (seed -> work): dst where src is seed
    cited_by_seed = set(edges[edges["src_work_id"].isin(seed_ids)]["dst_work_id"])

    wa_work = wa.merge(works[["work_id", "year", "coupling_community",
                              "is_seed"]], on="work_id", how="left")

    # --- per-author aggregates ------------------------------------------
    grp = wa_work.groupby("canon")
    agg = pd.DataFrame({
        "n_works": grp["work_id"].nunique(),
        "recent_works": grp.apply(
            lambda g: g[g["year"] >= RECENT_YEAR]["work_id"].nunique(),
            include_groups=False),
        "seed_authored": grp.apply(
            lambda g: g[g["is_seed"] == 1]["work_id"].nunique(),
            include_groups=False),
    })
    # cited-by-seed: how many of the author's works are cited by a seed
    cbs = (wa_work[wa_work["work_id"].isin(cited_by_seed)]
           .groupby("canon")["work_id"].nunique())
    agg["cited_by_seed"] = cbs
    agg["cited_by_seed"] = agg["cited_by_seed"].fillna(0)
    agg["seed_connectedness"] = agg["seed_authored"] + agg["cited_by_seed"]

    # --- topical fit -----------------------------------------------------
    topics = pd.read_sql_query("SELECT work_id, topic_name FROM topics", con)
    hint = topics["topic_name"].str.lower().fillna("")
    core_mask = hint.apply(lambda t: any(h in t for h in C.CORE_TOPIC_HINTS))
    core_works = set(topics[core_mask]["work_id"])
    agg["core_works"] = (wa_work[wa_work["work_id"].isin(core_works)]
                         .groupby("canon")["work_id"].nunique())
    agg["core_works"] = agg["core_works"].fillna(0)
    agg["topical_fit"] = (agg["core_works"] / agg["n_works"]).clip(0, 1)

    # --- centrality (coauthorship eigenvector, summed over merged ids) ---
    cn = pd.read_csv(C.EXPORTS / "coauthor_nodes.csv")
    cn["canon"] = cn["author_id"].map(canon).fillna(cn["author_id"])
    cent = cn.groupby("canon").agg(
        eigenvector=("eigenvector", "max"),
        degree=("degree", "max"),
        betweenness=("betweenness", "max")).reset_index().set_index("canon")
    agg = agg.join(cent)

    # --- dominant in-scope community ------------------------------------
    inscope = wa_work[wa_work["coupling_community"].isin(SCOPE_COMMUNITIES)]
    dom = (inscope.groupby("canon")["coupling_community"]
           .agg(lambda s: s.value_counts().idxmax()))
    agg["community"] = dom
    agg = agg[agg.index.isin(dom.index)]  # keep only in-scope researchers

    # --- openness --------------------------------------------------------
    try:
        ao = pd.read_sql_query("SELECT * FROM author_openness", con).set_index(
            "author_id")
        agg = agg.join(ao[["oa_share", "preprint_rate", "open_signal_rate",
                           "infra_score", "openness"]])
    except Exception:
        for col in ["oa_share", "preprint_rate", "open_signal_rate",
                    "infra_score", "openness"]:
            agg[col] = 0.0
    agg["openness"] = agg["openness"].fillna(0.0)

    # --- identity + contact route ---------------------------------------
    authors = pd.read_sql_query(
        "SELECT author_id, display_name, orcid, cited_by_count, "
        "last_institution_id, country FROM authors", con).set_index("author_id")
    inst = pd.read_sql_query(
        "SELECT inst_id, display_name, ror, country FROM institutions",
        con).set_index("inst_id")
    agg = agg.join(authors[["display_name", "orcid", "cited_by_count",
                            "last_institution_id", "country"]])
    agg["institution"] = agg["last_institution_id"].map(inst["display_name"])
    agg["inst_ror"] = agg["last_institution_id"].map(inst["ror"])

    # contacts join (if Stage F has run)
    contacts_path = C.EXPORTS / "contacts.csv"
    if contacts_path.exists():
        ct = pd.read_csv(contacts_path).set_index("author_id")
        agg = agg.join(ct[["email", "email_source_doi", "email_confidence",
                           "orcid_url", "institution_url"]], rsuffix="_ct")

    # --- composite score -------------------------------------------------
    agg["s_seed"] = norm01(agg["seed_connectedness"], log=True)
    agg["s_cent"] = norm01(agg["eigenvector"].fillna(0.0))
    agg["s_recent"] = norm01(agg["recent_works"], log=True)
    agg["s_topic"] = agg["topical_fit"].fillna(0.0)
    agg["s_open"] = agg["openness"].fillna(0.0)
    agg["outreach_score"] = (
        0.30 * agg["s_seed"] + 0.20 * agg["s_cent"] + 0.20 * agg["s_recent"] +
        0.15 * agg["s_topic"] + 0.15 * agg["s_open"])

    labels = community_label(
        json.loads((C.EXPORTS / "community_labels.json").read_text()))
    agg["cluster"] = agg["community"].map(labels)

    # community-0 sub-cluster + consciousness-adjacent flag (from subdivide.py)
    sub_path = C.EXPORTS / "community0_subclusters.csv"
    lab_path = C.EXPORTS / "community0_subcluster_labels.json"
    if sub_path.exists() and lab_path.exists():
        sub = pd.read_csv(sub_path)
        sublabs = json.loads(lab_path.read_text())
        consc_subs = {int(k) for k, v in sublabs.items()
                      if v.get("is_consciousness")}
        core_subs = {int(k) for k, v in sublabs.items() if v.get("is_core")}
        wa_sub = wa.merge(sub, on="work_id", how="inner")  # community-0 works
        dom_sub = (wa_sub.groupby("canon")["subcluster"]
                   .agg(lambda s: s.value_counts().idxmax()))
        agg["c0_subcluster"] = agg.index.map(dom_sub)
        agg["consciousness_adjacent"] = agg["c0_subcluster"].apply(
            lambda x: 1 if (pd.notna(x) and int(x) in consc_subs) else 0)
        strand = {int(k): v["label"] for k, v in sublabs.items()}
        agg["core_strand"] = agg["c0_subcluster"].apply(
            lambda x: strand.get(int(x)) if (pd.notna(x) and int(x) in core_subs)
            else "")
    else:
        agg["c0_subcluster"] = None
        agg["consciousness_adjacent"] = 0
        agg["core_strand"] = ""

    agg = agg.sort_values("outreach_score", ascending=False).reset_index()
    agg = agg.rename(columns={"index": "author_id", "canon": "author_id"})
    agg.insert(0, "rank", range(1, len(agg) + 1))

    cols = ["rank", "author_id", "display_name", "orcid", "institution",
            "country", "community", "cluster", "core_strand",
            "consciousness_adjacent", "n_works", "recent_works",
            "seed_connectedness", "eigenvector", "topical_fit", "openness",
            "oa_share", "preprint_rate", "open_signal_rate", "infra_score",
            "cited_by_count", "outreach_score"]
    for c in ["email", "email_source_doi", "email_confidence", "orcid_url",
              "institution_url"]:
        if c in agg.columns:
            cols.append(c)
    out = agg[[c for c in cols if c in agg.columns]]
    out.to_csv(C.EXPORTS / "researchers.csv", index=False)
    out.to_csv(C.OUTPUTS / "researchers.csv", index=False)

    # filtered views
    out.head(50).to_csv(C.EXPORTS / "researchers_top50.csv", index=False)
    (out.sort_values("openness", ascending=False).head(50)
     .to_csv(C.EXPORTS / "researchers_top_open.csv", index=False))
    (out[out["recent_works"] >= 3].head(50)
     .to_csv(C.EXPORTS / "researchers_rising.csv", index=False))
    # biophoton core + ROS wing only (communities 0 and 3) — the field proper,
    # re-ranked within itself so cavitation chemists don't crowd it out
    core = out[out["community"].isin([0, 3])].copy()
    core["rank"] = range(1, len(core) + 1)
    core.to_csv(C.EXPORTS / "researchers_biophoton_core.csv", index=False)
    core.head(50).to_csv(C.OUTPUTS / "researchers_biophoton_core_top50.csv",
                         index=False)

    print("=== Stage G: ranking ===")
    print(f"  ranked researchers (in-scope): {len(out)}")
    print(f"  top 10:")
    for r in out.head(10).itertuples():
        print(f"   {r.rank:>2}. {str(r.display_name)[:28]:28} "
              f"score={r.outreach_score:.3f} seed={r.seed_connectedness} "
              f"recent={r.recent_works} open={r.openness:.2f} "
              f"[{str(r.cluster)[:30]}]")
    with open(C.RUN_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n## Stage G — ranking\n\n- ranked researchers: {len(out)}\n")
    con.close()


if __name__ == "__main__":
    main()
