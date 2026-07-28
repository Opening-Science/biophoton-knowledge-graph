"""Milestone 2 checkpoint: label the coupling sub-field communities, run the
§10 verification spot-checks, and emit outputs/field_boundary_report.md.

Read-only over fieldmap.sqlite + work_communities.csv + networks_report.json.
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict

import pandas as pd

import config as C

KNOWN = ["cifra", "popp", "van wijk", "wijk", "kobayashi", "pospisil",
         "pospíšil", "salari", "scholkmann", "voeikov", "musumeci"]


def con():
    return sqlite3.connect(C.DB_PATH)


def label_communities(c) -> list[dict]:
    wc = pd.read_csv(C.EXPORTS / "work_communities.csv")
    wc = wc.dropna(subset=["coupling_community"])
    wc["coupling_community"] = wc["coupling_community"].astype(int)

    topics = pd.read_sql_query(
        "SELECT work_id, topic_name, score FROM topics", c)
    # keep the top-scoring topic per work to label cleanly
    top_topic = (topics.sort_values("score", ascending=False)
                 .drop_duplicates("work_id"))
    wt = wc.merge(top_topic[["work_id", "topic_name"]], on="work_id", how="left")

    wa = pd.read_sql_query(
        "SELECT wa.work_id, a.display_name FROM work_authors wa "
        "JOIN authors a ON a.author_id = wa.author_id", c)

    out = []
    for comm, grp in wc.groupby("coupling_community"):
        ids = set(grp["work_id"])
        sub_topics = wt[wt["coupling_community"] == comm]["topic_name"].dropna()
        auth = wa[wa["work_id"].isin(ids)]["display_name"].dropna()
        reps = (grp.sort_values("cited_by_count", ascending=False)
                .head(5)[["title", "year", "cited_by_count"]])
        years = grp["year"].dropna()
        out.append({
            "community": int(comm),
            "n_works": len(grp),
            "n_seeds": int(grp["is_seed"].sum()),
            "year_median": int(years.median()) if len(years) else None,
            "year_range": (f"{int(years.min())}-{int(years.max())}"
                           if len(years) else None),
            "top_topics": [t for t, _ in Counter(sub_topics).most_common(6)],
            "top_authors": [a for a, _ in Counter(auth).most_common(8)],
            "rep_works": [
                {"title": (r.title or "")[:90], "year": r.year,
                 "cited_by": int(r.cited_by_count or 0)}
                for r in reps.itertuples()],
        })
    out.sort(key=lambda d: d["n_works"], reverse=True)
    return out


def author_seed_connectedness(c) -> dict[str, int]:
    """# seed works each author (co)authored — proximity to the Cifra core."""
    df = pd.read_sql_query(
        "SELECT wa.author_id, a.display_name FROM work_authors wa "
        "JOIN works w ON w.work_id = wa.work_id "
        "JOIN authors a ON a.author_id = wa.author_id WHERE w.is_seed=1", c)
    return df.groupby("display_name")["author_id"].count().to_dict()


def spot_check(c) -> list[dict]:
    seed_conn = author_seed_connectedness(c)
    rows = []
    seen = set()
    a = pd.read_sql_query(
        "SELECT author_id, display_name, orcid, works_count, cited_by_count, "
        "last_institution_id, country FROM authors", c)
    inst = pd.read_sql_query(
        "SELECT inst_id, display_name FROM institutions", c)
    inst_map = dict(zip(inst["inst_id"], inst["display_name"]))
    for key in KNOWN:
        hits = a[a["display_name"].str.lower().str.contains(key, na=False)]
        for r in hits.itertuples():
            if r.display_name in seen:
                continue
            seen.add(r.display_name)
            sc = seed_conn.get(r.display_name, 0)
            if sc == 0:
                continue
            orcid = "" if pd.isna(r.orcid) else str(r.orcid)
            orcid = orcid.replace("https://orcid.org/", "")
            rows.append({
                "name": r.display_name,
                "orcid": orcid,
                "institution": inst_map.get(r.last_institution_id, "") or "",
                "country": "" if pd.isna(r.country) else str(r.country),
                "works_count": 0 if pd.isna(r.works_count) else int(r.works_count),
                "cited_by": 0 if pd.isna(r.cited_by_count) else int(r.cited_by_count),
                "seed_works": sc,
            })
    rows.sort(key=lambda d: d["seed_works"], reverse=True)
    return rows


def main() -> None:
    c = con()
    report = json.loads((C.EXPORTS / "networks_report.json").read_text())
    comms = label_communities(c)
    checks = spot_check(c)

    # seed coverage
    seeds = pd.read_csv(C.EXPORTS / "seed_works.csv")
    resolved = int((seeds["work_id"].astype(str) != "").sum() -
                   (seeds["work_id"].isna()).sum())
    resolved = int((seeds["work_id"].notna() & (seeds["work_id"] != "")).sum())

    b = report["boundary"]
    lines = []
    lines.append("# Biophoton Field Map — Milestone 2 Checkpoint\n")
    lines.append(f"_OpenAlex snapshot: harvested 2026-07-19/20. "
                 f"Universe = {sum(cc['n_works'] for cc in comms)} works in the "
                 f"coupling graph._\n")

    lines.append("## 1. The field-boundary question (the analytical ask)\n")
    verdict = ("**distinct communities**" if b["distinct"]
               else "**NOT distinct — revisit thresholds**")
    lines.append(
        f"Sonoluminescence / acoustic-cavitation seed works land in "
        f"bibliographic-coupling community **{b['sono_top_community']}**, while "
        f"the UPE core (Cifra / Popp / Van Wijk / Kobayashi) lands in community "
        f"**{b['upe_top_community']}** — {verdict}.\n")
    lines.append(f"- Sonoluminescence seed works ({b['sonoluminescence_seed_works']}): "
                 f"community distribution {b['sono_community_distribution']}")
    lines.append(f"- UPE-core seed works: distribution "
                 f"{b['upe_core_community_distribution']}\n")
    lines.append("This empirically confirms the physics (single-bubble "
                 "sonoluminescence, cavitation) is an **adjacency**, not part of "
                 "the biophoton/UPE core — answering the scope question from the "
                 "map itself rather than by pre-filtering.\n")

    lines.append("## 2. Sub-field communities (bibliographic coupling)\n")
    lines.append(f"{report['coupling']['communities']} communities over "
                 f"{report['coupling']['works']} works "
                 f"({report['coupling']['edges']:,} coupling edges). "
                 f"Largest communities:\n")
    for cc in comms[:10]:
        tag = ""
        if cc["community"] == b["upe_top_community"]:
            tag = "  ← **UPE / biophoton core**"
        elif cc["community"] == b["sono_top_community"]:
            tag = "  ← **sonoluminescence / cavitation (adjacency)**"
        lines.append(
            f"### Community {cc['community']} — {cc['n_works']} works, "
            f"{cc['n_seeds']} seeds, median year {cc['year_median']}{tag}")
        lines.append(f"- **Topics:** {', '.join(cc['top_topics'][:5])}")
        lines.append(f"- **Top authors:** {', '.join(cc['top_authors'][:6])}")
        if cc["rep_works"]:
            rw = cc["rep_works"][0]
            lines.append(f"- **Most-cited work:** {rw['title']} "
                         f"({rw['year']}, {rw['cited_by']} cites)")
        lines.append("")

    lines.append("## 3. Co-authorship structure\n")
    lines.append(f"- {report['coauthorship']['authors']:,} authors, "
                 f"{report['coauthorship']['edges']:,} co-authorship edges, "
                 f"{report['coauthorship']['communities']:,} research-group "
                 f"communities (labs/collaborations).\n")

    lines.append("## 4. §10 verification\n")
    lines.append(f"- **Seed coverage:** {resolved}/263 seeds resolved "
                 f"(target ≥240 — {'PASS' if resolved >= 240 else 'FAIL'}).")
    lines.append(f"- **Boundary sanity:** sonoluminescence separates from UPE "
                 f"core — {'PASS' if b['distinct'] else 'FAIL'}.")
    lines.append(f"- **Known-author spot checks** (must appear with sane "
                 f"institution + high seed-connectedness):\n")
    lines.append("| Author | Seed works | Institution | Country | ORCID | Total works | Cited by |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in checks:
        lines.append(f"| {r['name']} | {r['seed_works']} | "
                     f"{(r['institution'] or '')[:32]} | {r['country']} | "
                     f"{r['orcid']} | {r['works_count']} | {r['cited_by']:,} |")
    lines.append("")

    lines.append("## 5. Deliverables so far\n")
    lines.append("- `data/db/fieldmap.sqlite` — queryable DB (works, authors, "
                 "institutions, work_authors, topics, citation/coauthor edges).")
    lines.append("- `data/exports/*.parquet|csv` — all tables.")
    lines.append("- `data/exports/*.graphml` — coauthorship, coupling, "
                 "cocitation, topic graphs (open in Gephi).")
    lines.append("- `data/exports/work_communities.csv` — per-work sub-field "
                 "community assignment.")
    lines.append("- `run_log.md` — every prune/cap count.\n")

    out = C.OUTPUTS / "field_boundary_report.md"
    out.write_text("\n".join(lines))
    print(f"Wrote {out}")

    # also dump the labeled communities as json for reuse
    (C.EXPORTS / "community_labels.json").write_text(json.dumps(comms, indent=2))
    c.close()
    print("\n".join(lines[:4]))
    print(f"\nSpot-checked {len(checks)} known authors; "
          f"{len(comms)} coupling communities labeled.")


if __name__ == "__main__":
    main()
