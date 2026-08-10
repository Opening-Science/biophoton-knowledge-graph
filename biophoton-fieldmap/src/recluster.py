"""Re-cluster the coupling graph following current science-mapping practice.

Three changes against `networks.py`, each with a citation rather than a hunch:

1. **Fractional counting** of coupling links instead of raw shared-reference
   counts (Perianes-Rodríguez, Waltman & van Eck, 2016). Removes hub-reference
   domination without an arbitrary cutoff. See `coupling.py`.

2. **Constant Potts Model** instead of `RBConfigurationVertexPartition`
   (Traag, Van Dooren & Nesterov, 2011; Traag, Waltman & van Eck, 2019). CPM is
   resolution-limit free, so a giant 5,193-work blob is no longer an artefact of
   the quality function; its resolution parameter is an interpretable internal
   link-density threshold rather than an arbitrary knob.

3. **Consensus stability** over repeated Leiden runs with different random
   seeds. Leiden is stochastic; a partition reported without a stability figure
   is a partition whose reproducibility is unknown. Per work we report the share
   of its reference cluster that stays with it across runs.

Bibliographic coupling itself is kept deliberately: Waltman, Boyack, Colavizza
& van Eck (2020) find it yields more accurate clusterings than direct citation
or co-citation.

    python src/recluster.py --sweep              # choose a resolution on evidence
    python src/recluster.py --resolution 0.004   # final run + report
"""
from __future__ import annotations

import argparse
import json
import sqlite3

import igraph as ig
import leidenalg as la
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

import config as C
import coupling as CP

SONO_HINTS = ("sonolumin", "cavitation", "acoustic", "bubble")
UPE_HINTS = ("photon", "luminescen", "ultraweak", "ultra-weak")
# Research contributions only, as in the CWTS publication-level classification.
# The universe otherwise carries 40 paratext, 43 reference-entry, 34 book-review,
# 17 editorial, 7 erratum and 6 peer-review records that are not research works
# and should not be clustered as if they were.
RESEARCH_TYPES = ("article", "review", "conference-paper", "book-chapter",
                  "preprint", "book", "dissertation", "report", "data-paper")
SWEEP = (0.0005, 0.001, 0.002, 0.004, 0.008, 0.016, 0.032)
RUNS = 10
BASE_SEED = 42

OUT_CSV = C.EXPORTS / "work_communities_v2.csv"
OUT_MD = C.OUTPUTS / "recluster_comparison.md"
OUT_JSON = C.EXPORTS / "recluster_report.json"


# --------------------------------------------------------------------------- #
def load(research_types_only: bool = False):
    con = sqlite3.connect(str(C.DB_PATH))
    edges = pd.read_sql_query(
        "SELECT src_work_id, dst_work_id FROM citation_edges", con)
    works = pd.read_sql_query(
        "SELECT work_id, title, year, type, cited_by_count, is_seed, hop "
        "FROM works", con)
    con.close()
    if research_types_only:
        keep = works.loc[works["type"].isin(RESEARCH_TYPES) |
                         (works["is_seed"] == 1), "work_id"]
        dropped = len(works) - len(keep)
        works = works[works["work_id"].isin(set(keep))]
        edges = edges[edges["src_work_id"].isin(set(keep))]
        print(f"  research-types filter: dropped {dropped} non-research records")
    return edges, works


def partition(g: ig.Graph, quality: str, resolution: float, seed: int):
    cls = (la.CPMVertexPartition if quality == "cpm"
           else la.RBConfigurationVertexPartition)
    return la.find_partition(g, cls, weights="weight",
                             resolution_parameter=resolution, seed=seed)


def stability(reference: list[int], runs: list[list[int]]) -> np.ndarray:
    """Per-node consensus: mean over runs of the share of the node's reference
    cluster that is still co-assigned with it."""
    ref = np.asarray(reference)
    ref_size = np.bincount(ref)[ref]
    acc = np.zeros(len(ref), dtype=np.float64)
    for r in runs:
        run = np.asarray(r)
        df = pd.DataFrame({"ref": ref, "run": run})
        joint = df.groupby(["ref", "run"]).size()
        acc += joint.loc[list(zip(ref, run))].to_numpy() / ref_size
    return acc / len(runs)


def describe(df: pd.DataFrame, col: str, hints) -> pd.Series:
    t = df["title"].fillna("").str.lower()
    return t.str.contains("|".join(hints), regex=True)


# --------------------------------------------------------------------------- #
def sweep(g, works, work_ids, quality, resolutions):
    seeds = set(works.loc[works["is_seed"] == 1, "work_id"])
    idx = pd.Series(work_ids)
    is_seed = idx.isin(seeds).to_numpy()
    upe = works.set_index("work_id").loc[work_ids]
    upe_title = describe(upe.reset_index(), "title", UPE_HINTS).to_numpy()

    rows = []
    for res in resolutions:
        p = partition(g, quality, res, BASE_SEED)
        m = np.asarray(p.membership)
        sizes = np.bincount(m)
        seed_counts = np.bincount(m[is_seed], minlength=len(sizes))
        home = int(seed_counts.argmax())
        inhome = m == home
        rows.append({
            "resolution": res,
            "clusters": int(len(sizes)),
            "clusters>=20": int((sizes >= 20).sum()),
            "largest": int(sizes.max()),
            "seed_home": home,
            "home_works": int(inhome.sum()),
            "home_seeds": int(seed_counts[home]),
            "seed_capture": round(seed_counts[home] / is_seed.sum(), 3),
            "home_upe_share": round(float(upe_title[inhome].mean()), 3),
        })
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--counting", choices=("fractional", "full"),
                    default="fractional")
    ap.add_argument("--quality", choices=("cpm", "rb"), default="cpm")
    ap.add_argument("--resolution", type=float, default=0.004)
    ap.add_argument("--min-weight", type=float, default=0.0)
    ap.add_argument("--assoc-strength", action="store_true")
    ap.add_argument("--runs", type=int, default=RUNS)
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--research-types-only", action="store_true",
                    help="drop paratext, errata, peer-review and other "
                         "non-research records before clustering")
    a = ap.parse_args()

    edges, works = load(a.research_types_only)
    print("building incidence matrix...")
    A, work_ids_all, n_citers = CP.build_matrix(edges)
    stats = CP.reference_stats(n_citers)
    print(f"  {stats['shared_references']:,} shared references; "
          f"{stats['refs_for_63pct_of_pairs']} of them carry 63% of full-counting "
          f"pair mass (largest: {stats['largest_reference_citers']:,} citers)")

    print(f"coupling matrix ({a.counting} counting"
          f"{', association strength' if a.assoc_strength else ''})...")
    Cm = CP.coupling_matrix(A, n_citers, counting=a.counting,
                            assoc_strength=a.assoc_strength,
                            min_weight=a.min_weight)
    pairs, w, work_ids = CP.to_edges(Cm, work_ids_all)
    g = ig.Graph(n=len(work_ids))
    g.vs["name"] = work_ids
    g.add_edges([tuple(p) for p in pairs])
    g.es["weight"] = w.tolist()
    print(f"  graph: {g.vcount():,} nodes, {g.ecount():,} edges, "
          f"median weight {np.median(w):.5f}")

    if a.sweep:
        tbl = sweep(g, works, work_ids, a.quality, SWEEP)
        print(f"\n=== resolution sweep ({a.quality}, {a.counting} counting) ===")
        print(tbl.to_string(index=False))
        print("\nPick the resolution that maximises seed capture and UPE share "
              "without collapsing into one blob, then rerun with --resolution.")
        return

    print(f"Leiden ({a.quality}, resolution {a.resolution}, "
          f"{a.runs} runs for stability)...")
    ref = partition(g, a.quality, a.resolution, BASE_SEED)
    runs = [partition(g, a.quality, a.resolution, BASE_SEED + i).membership
            for i in range(1, a.runs)]
    stab = stability(ref.membership, runs)
    aris = [adjusted_rand_score(ref.membership, r) for r in runs]
    nmis = [normalized_mutual_info_score(ref.membership, r) for r in runs]
    print(f"  {len(set(ref.membership))} clusters · ARI vs reruns "
          f"{np.mean(aris):.3f} ± {np.std(aris):.3f} · mean node stability "
          f"{stab.mean():.3f}")

    assign = pd.DataFrame({"work_id": work_ids,
                           "community_v2": ref.membership,
                           "stability": stab.round(4)})
    df = works.merge(assign, on="work_id", how="left")
    old = pd.read_csv(C.EXPORTS / "work_communities.csv")[
        ["work_id", "coupling_community"]]
    df = df.merge(old, on="work_id", how="left")
    df.to_csv(OUT_CSV, index=False)

    # ---- where the seeds and the boundary land --------------------------
    seeds = df[df["is_seed"] == 1].copy()
    seeds["sono"] = describe(seeds, "title", SONO_HINTS)
    seed_home = int(seeds.loc[~seeds["sono"], "community_v2"].value_counts().index[0])
    sono_home = int(seeds.loc[seeds["sono"], "community_v2"].value_counts().index[0])
    home = df[df["community_v2"] == seed_home]
    old_core = df[df["coupling_community"] == 0]
    upe_share = lambda d: float(describe(d, "title", UPE_HINTS).mean())

    report = {
        "params": vars(a), "reference_stats": stats,
        "graph": {"nodes": g.vcount(), "edges": g.ecount()},
        "clusters": len(set(ref.membership)),
        "ari_mean": round(float(np.mean(aris)), 4),
        "ari_std": round(float(np.std(aris)), 4),
        "nmi_mean": round(float(np.mean(nmis)), 4),
        "node_stability_mean": round(float(stab.mean()), 4),
        "node_stability_below_0.5": int((stab < 0.5).sum()),
        "unassigned": int(df["community_v2"].isna().sum()),
        "seed_home": seed_home, "sono_home": sono_home,
        "boundary_distinct": seed_home != sono_home,
        "home_works": len(home), "home_seeds": int((home["is_seed"] == 1).sum()),
        "home_upe_share": round(upe_share(home), 3),
        "old_c0_upe_share": round(upe_share(old_core), 3),
        "home_stability_mean": round(float(home["stability"].mean()), 4),
    }
    OUT_JSON.write_text(json.dumps(report, indent=2))

    L = [
        "# Re-clustering comparison — fractional counting + CPM\n",
        f"_{a.counting} counting · {a.quality.upper()} · resolution "
        f"{a.resolution} · {a.runs} Leiden runs · base seed {BASE_SEED}_\n",
        "Method choices and their sources are documented in "
        "[`src/coupling.py`](../src/coupling.py) and "
        "[`src/recluster.py`](../src/recluster.py); the reasoning is in "
        "[`docs/CLUSTERING_STRATEGY.md`](../../docs/CLUSTERING_STRATEGY.md).\n",
        "## Graph\n",
        "| | current (`networks.py`) | v2 |", "|---|---|---|",
        f"| counting | full, weight ≥ 2 | {a.counting} |",
        f"| quality function | RBConfiguration | {a.quality.upper()} |",
        "| nodes | 14,807 | {:,} |".format(g.vcount()),
        "| edges | 2,392,824 | {:,} |".format(g.ecount()),
        f"| clusters | 11 | {report['clusters']} |",
        f"| works unassigned | 3,548 | {report['unassigned']:,} |",
        f"| largest cluster | 5,193 | {int(df['community_v2'].value_counts().iloc[0]):,} |",
        f"| ARI across reruns | not measured | **{report['ari_mean']:.3f} ± {report['ari_std']:.3f}** |",
        f"| mean node stability | not measured | **{report['node_stability_mean']:.3f}** |\n",
        "## The UPE home\n",
        f"| | current community 0 | v2 community {seed_home} |", "|---|---|---|",
        f"| works | {len(old_core):,} | {len(home):,} |",
        f"| seeds | {int((old_core['is_seed']==1).sum())} | {report['home_seeds']} |",
        f"| median year | {int(old_core['year'].dropna().median())} | "
        f"{int(home['year'].dropna().median())} |",
        f"| photon/luminescence titles | {report['old_c0_upe_share']*100:.0f}% | "
        f"**{report['home_upe_share']*100:.0f}%** |",
        f"| mean node stability | — | {report['home_stability_mean']:.3f} |\n",
        "## Field boundary (the Milestone-2 finding)\n",
        f"Sonoluminescence seeds concentrate in v2 community **{sono_home}**, "
        f"non-sonoluminescence seeds in **{seed_home}** — "
        f"{'still distinct' if report['boundary_distinct'] else 'NOT distinct — revisit'}.\n",
        "## Where the ten citation magnets went\n",
        "| work | cites | current | v2 |", "|---|---|---|---|"]
    for r in old_core.nlargest(10, "cited_by_count").itertuples():
        new = "dropped" if pd.isna(r.community_v2) else int(r.community_v2)
        L.append(f"| {str(r.title)[:60]} | {r.cited_by_count:,} | 0 | {new} |")
    L += ["", "## Where the current community 0 dispersed to\n",
          "| v2 community | works from old c0 |", "|---|---|"]
    for k, v in old_core["community_v2"].value_counts(dropna=False).head(8).items():
        L.append(f"| {'dropped' if pd.isna(k) else int(k)} | {int(v):,} |")
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"\nWrote {OUT_CSV}\nWrote {OUT_MD}\nWrote {OUT_JSON}")
    print(json.dumps({k: report[k] for k in (
        "clusters", "ari_mean", "node_stability_mean", "unassigned",
        "seed_home", "home_works", "home_seeds", "home_upe_share",
        "boundary_distinct")}, indent=2))


if __name__ == "__main__":
    main()
