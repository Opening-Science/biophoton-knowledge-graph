"""Build a compact co-authorship network for the in-app Field Map graph.

Top researchers as nodes (archipelago layout by sub-field, positions baked in),
co-authorship edges among them. Emitted as a small JSON for the osf-app module
to serve behind auth. Reuses report.py's layout.
"""
from __future__ import annotations

import json
import math
import sqlite3

import pandas as pd

import config as C
from report import archipelago_layout, COMM, OTHER

TOP_N = 320
MAX_EDGES = 1800
OUT = C.OUTPUTS / "fieldmap-network.json"


def main():
    con = sqlite3.connect(C.DB_PATH)
    r = pd.read_csv(C.EXPORTS / "researchers.csv").head(TOP_N).copy()
    r["community"] = r["community"].fillna(-1).astype(int)
    ids = set(r["author_id"])
    ce = pd.read_sql_query(
        "SELECT author_a, author_b, weight FROM coauthor_edges", con)
    ce = ce[ce["author_a"].isin(ids) & ce["author_b"].isin(ids)]
    ce = ce.sort_values("weight", ascending=False).head(MAX_EDGES)
    con.close()
    edges = [(a, b, float(w)) for a, b, w in
             zip(ce["author_a"], ce["author_b"], ce["weight"])]

    pos = archipelago_layout(r[["author_id", "community"]], edges)
    ev = r["eigenvector"].fillna(0).astype(float)
    evmax = ev.max() or 1.0

    nodes, idx = [], {}
    for row in r.itertuples():
        if row.author_id not in pos:
            continue
        idx[row.author_id] = len(nodes)
        x, y = pos[row.author_id]
        size = 4 + 14 * math.sqrt(
            max(0.0, float(getattr(row, "eigenvector", 0) or 0)) / evmax)
        nodes.append({
            "n": str(row.display_name),
            "x": round(x, 1), "y": round(y, 1),
            "c": int(row.community), "s": round(size, 1),
            "o": round(float(row.openness or 0), 2),
            "inst": (str(row.institution) if pd.notna(row.institution) else "")[:40],
            "cl": str(row.cluster) if pd.notna(row.cluster) else "",
        })
    elist = [[idx[a], idx[b]] for a, b, _ in edges if a in idx and b in idx]
    palette = {str(k): v[1] for k, v in COMM.items()}
    palette["-1"] = OTHER[1]
    names = {str(k): v[0] for k, v in COMM.items()}
    names["-1"] = OTHER[0]

    data = {"nodes": nodes, "edges": elist, "palette": palette, "names": names,
            "snapshot": "2026-07"}
    OUT.write_text(json.dumps(data, separators=(",", ":")))
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB, "
          f"{len(nodes)} nodes, {len(elist)} edges)")


if __name__ == "__main__":
    main()
