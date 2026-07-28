"""Stage D — build networks and Leiden communities from the SQLite DB.

Graphs (igraph):
  1. Co-authorship (author nodes, shared-work edges) -> research groups.
  2. Bibliographic coupling (work-work, shared references).
  3. Co-citation (work-work, co-cited by a later work).
  4. Topic co-occurrence -> thematic map.
Cluster each with leidenalg (RBConfigurationVertexPartition). Compute
per-author centralities. Export GraphML/GEXF + node/edge CSVs. Explicitly
report which community the sonoluminescence seed set lands in (the empirical
answer to the field-boundary question, spec §10).
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from itertools import combinations

import igraph as ig
import leidenalg as la
import pandas as pd

import config as C

RES = 1.0  # Leiden resolution (tunable)
SONO_HINTS = ("sonolumin", "cavitation", "acoustic", "bubble")


def con():
    return sqlite3.connect(C.DB_PATH)


# --------------------------------------------------------------------------
def build_coauthorship(c) -> ig.Graph:
    wa = pd.read_sql_query(
        "SELECT work_id, author_id FROM work_authors", c)
    by_work = wa.groupby("work_id")["author_id"].apply(list)
    weights: dict[tuple[str, str], int] = defaultdict(int)
    for authors in by_work:
        uniq = sorted(set(authors))
        for a, b in combinations(uniq, 2):
            weights[(a, b)] += 1
    nodes = sorted({a for pair in weights for a in pair} |
                   set(wa["author_id"].unique()))
    idx = {n: i for i, n in enumerate(nodes)}
    g = ig.Graph(n=len(nodes))
    g.vs["name"] = nodes
    edges = [(idx[a], idx[b]) for (a, b) in weights]
    g.add_edges(edges)
    g.es["weight"] = list(weights.values())
    return g


def build_coupling(c) -> ig.Graph:
    """Bibliographic coupling: works sharing >=1 referenced work. Weight =
    number of shared references (edges with weight>=2 kept to control density)."""
    edges = pd.read_sql_query(
        "SELECT src_work_id, dst_work_id FROM citation_edges", c)
    refs_by_src = edges.groupby("src_work_id")["dst_work_id"].apply(set)
    # invert: for each referenced work, which srcs cite it
    citers_of: dict[str, list[str]] = defaultdict(list)
    for src, dsts in refs_by_src.items():
        for d in dsts:
            citers_of[d].append(src)
    weights: dict[tuple[str, str], int] = defaultdict(int)
    for d, srcs in citers_of.items():
        if len(srcs) < 2:
            continue
        for a, b in combinations(sorted(set(srcs)), 2):
            weights[(a, b)] += 1
    weights = {k: v for k, v in weights.items() if v >= 2}
    return _graph_from_weights(weights)


def build_cocitation(c) -> ig.Graph:
    """Co-citation: two works co-cited by a later work. Weight = # co-citers."""
    edges = pd.read_sql_query(
        "SELECT src_work_id, dst_work_id FROM citation_edges", c)
    refs_by_src = edges.groupby("src_work_id")["dst_work_id"].apply(set)
    weights: dict[tuple[str, str], int] = defaultdict(int)
    for src, dsts in refs_by_src.items():
        dl = sorted(d for d in dsts)
        if len(dl) < 2 or len(dl) > 400:  # skip pathological ref-lists
            continue
        for a, b in combinations(dl, 2):
            weights[(a, b)] += 1
    weights = {k: v for k, v in weights.items() if v >= 2}
    return _graph_from_weights(weights)


def build_topic_cooccurrence(c) -> ig.Graph:
    tp = pd.read_sql_query(
        "SELECT work_id, topic_id, topic_name FROM topics", c)
    name = dict(zip(tp["topic_id"], tp["topic_name"]))
    by_work = tp.groupby("work_id")["topic_id"].apply(list)
    weights: dict[tuple[str, str], int] = defaultdict(int)
    for topics in by_work:
        for a, b in combinations(sorted(set(topics)), 2):
            weights[(a, b)] += 1
    g = _graph_from_weights(weights)
    if g.vcount():
        g.vs["label"] = [name.get(n, n) for n in g.vs["name"]]
    return g


def _graph_from_weights(weights: dict[tuple[str, str], int]) -> ig.Graph:
    nodes = sorted({a for pair in weights for a in pair})
    idx = {n: i for i, n in enumerate(nodes)}
    g = ig.Graph(n=len(nodes))
    g.vs["name"] = nodes
    g.add_edges([(idx[a], idx[b]) for (a, b) in weights])
    g.es["weight"] = list(weights.values())
    return g


def leiden(g: ig.Graph) -> list[int]:
    if g.vcount() == 0 or g.ecount() == 0:
        return [0] * g.vcount()
    part = la.find_partition(
        g, la.RBConfigurationVertexPartition,
        weights="weight", resolution_parameter=RES, seed=42)
    return part.membership


# --------------------------------------------------------------------------
def main() -> None:
    c = con()
    report: dict = {}

    # --- co-authorship ---------------------------------------------------
    print("Building co-authorship graph...")
    ga = build_coauthorship(c)
    ga.vs["community"] = leiden(ga)
    if ga.vcount():
        ga.vs["degree"] = ga.degree()
        ga.vs["betweenness"] = ga.betweenness()
        ev = ga.eigenvector_centrality(weights="weight") if ga.ecount() else [0]*ga.vcount()
        ga.vs["eigenvector"] = ev
    names = pd.read_sql_query("SELECT author_id, display_name FROM authors", c)
    name_map = dict(zip(names["author_id"], names["display_name"]))
    coauth_nodes = pd.DataFrame({
        "author_id": ga.vs["name"],
        "display_name": [name_map.get(a) for a in ga.vs["name"]],
        "community": ga.vs["community"],
        "degree": ga.vs["degree"] if "degree" in ga.vs.attributes() else 0,
        "betweenness": ga.vs["betweenness"] if "betweenness" in ga.vs.attributes() else 0,
        "eigenvector": ga.vs["eigenvector"] if "eigenvector" in ga.vs.attributes() else 0,
    })
    coauth_nodes.to_csv(C.EXPORTS / "coauthor_nodes.csv", index=False)
    ga.write_graphml(str(C.EXPORTS / "coauthorship.graphml"))
    report["coauthorship"] = {
        "authors": ga.vcount(), "edges": ga.ecount(),
        "communities": len(set(ga.vs["community"])) if ga.vcount() else 0}

    # materialize coauthor_edges into the DB
    cur = c.cursor()
    cur.execute("DROP TABLE IF EXISTS coauthor_edges")
    cur.execute("CREATE TABLE coauthor_edges(author_a TEXT, author_b TEXT, weight INTEGER)")
    for e in ga.es:
        cur.execute("INSERT INTO coauthor_edges VALUES (?,?,?)",
                    (ga.vs[e.source]["name"], ga.vs[e.target]["name"], e["weight"]))
    c.commit()

    # --- bibliographic coupling -----------------------------------------
    print("Building bibliographic coupling graph...")
    gc = build_coupling(c)
    gc.vs["community"] = leiden(gc)
    gc.write_graphml(str(C.EXPORTS / "coupling.graphml"))
    report["coupling"] = {
        "works": gc.vcount(), "edges": gc.ecount(),
        "communities": len(set(gc.vs["community"])) if gc.vcount() else 0}

    # --- co-citation -----------------------------------------------------
    print("Building co-citation graph...")
    gco = build_cocitation(c)
    gco.vs["community"] = leiden(gco)
    gco.write_graphml(str(C.EXPORTS / "cocitation.graphml"))
    report["cocitation"] = {
        "works": gco.vcount(), "edges": gco.ecount(),
        "communities": len(set(gco.vs["community"])) if gco.vcount() else 0}

    # --- topic co-occurrence --------------------------------------------
    print("Building topic co-occurrence graph...")
    gt = build_topic_cooccurrence(c)
    gt.vs["community"] = leiden(gt)
    gt.write_graphml(str(C.EXPORTS / "topic_cooccurrence.graphml"))
    report["topics"] = {
        "topics": gt.vcount(), "edges": gt.ecount(),
        "communities": len(set(gt.vs["community"])) if gt.vcount() else 0}

    # --- work-level community table (from coupling) ----------------------
    work_meta = pd.read_sql_query(
        "SELECT work_id, title, year, is_seed, hop, cited_by_count FROM works", c)
    coup_comm = dict(zip(gc.vs["name"], gc.vs["community"])) if gc.vcount() else {}
    work_meta["coupling_community"] = work_meta["work_id"].map(coup_comm)
    work_meta.to_csv(C.EXPORTS / "work_communities.csv", index=False)

    # --- boundary question: where does sonoluminescence land? -----------
    # Find seed works whose topic/title marks them sonoluminescence.
    sono_sql = " OR ".join(["LOWER(title) LIKE '%%%s%%'" % h for h in SONO_HINTS])
    sono_works = pd.read_sql_query(
        f"SELECT work_id, title FROM works WHERE is_seed=1 AND ({sono_sql})", c)
    sono_comms = [coup_comm.get(w) for w in sono_works["work_id"]
                  if coup_comm.get(w) is not None]
    from collections import Counter
    sono_dist = Counter(sono_comms)

    # UPE core reference: Cifra/Popp/Van Wijk seed works' communities
    core_authors_sql = """
      SELECT DISTINCT wa.work_id FROM work_authors wa
      JOIN authors a ON a.author_id = wa.author_id
      JOIN works w ON w.work_id = wa.work_id
      WHERE w.is_seed=1 AND (
        LOWER(a.display_name) LIKE '%cifra%' OR
        LOWER(a.display_name) LIKE '%popp%' OR
        LOWER(a.display_name) LIKE '%van wijk%' OR
        LOWER(a.display_name) LIKE '%kobayashi%')
    """
    core_works = pd.read_sql_query(core_authors_sql, c)
    core_comms = Counter(coup_comm.get(w) for w in core_works["work_id"]
                         if coup_comm.get(w) is not None)

    report["boundary"] = {
        "sonoluminescence_seed_works": len(sono_works),
        "sono_community_distribution": {str(k): v for k, v in sono_dist.items()},
        "upe_core_community_distribution": {str(k): v for k, v in core_comms.items()},
        "sono_top_community": (sono_dist.most_common(1)[0][0]
                               if sono_dist else None),
        "upe_top_community": (core_comms.most_common(1)[0][0]
                              if core_comms else None),
    }
    report["boundary"]["distinct"] = (
        report["boundary"]["sono_top_community"]
        != report["boundary"]["upe_top_community"]
        and report["boundary"]["sono_top_community"] is not None)

    c.close()
    (C.EXPORTS / "networks_report.json").write_text(json.dumps(report, indent=2))

    print("\n=== Stage D: networks ===")
    print(json.dumps(report, indent=2))

    with open(C.RUN_LOG, "a", encoding="utf-8") as f:
        f.write("\n## Stage D — networks\n\n```json\n")
        f.write(json.dumps(report, indent=2))
        f.write("\n```\n")


if __name__ == "__main__":
    main()
