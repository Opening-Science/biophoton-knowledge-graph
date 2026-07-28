"""Stage H — synthesis deliverables (spec §9).

  * outputs/field_state.md      — book chapter-0 scaffold: sub-field narrative,
    key labs & geography, timeline, open-vs-closed analysis, gaps.
  * outputs/knowledge_map.html  — interactive force graph of the top researchers,
    colored by sub-field community, sized by centrality, openness on the border.

Read-only over the DB + Stage D/E/G exports.
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter

import pandas as pd

import config as C

SCOPE = {0: "UPE / biophoton core", 3: "ROS / redox / biochemiluminescence",
         1: "sonochemistry / acoustic cavitation", 2: "bubble & fluid physics",
         4: "sonoluminescence physics", 6: "nanobubbles"}
CITATION_MAGNET = 8000  # drop reps above this (general-science outliers)


def con():
    return sqlite3.connect(C.DB_PATH)


def load_communities() -> list[dict]:
    return json.loads((C.EXPORTS / "community_labels.json").read_text())


# Human-readable names for the recurring UPE-core sub-strands. Keyed first on a
# distinctive author (most reliable), then on a topic substring; falls back to
# the raw topic label.
STRAND_BY_AUTHOR = [
    (("volodyaev", "fels", "savelev"), "cellular communication through light"),
    (("scordino", "musumeci", "grasso"), "delayed luminescence & photosynthesis"),
    (("gallep", "niggli", "iyozumi"), "biophoton imaging & plant/animal UPE"),
    (("beloussov", "chang", "bajpai"), "coherence theory (Popp school)"),
    (("bókkon", "bokkon"), "retinal & brain single-photon signalling"),
    (("simon", "dai"), "neural / brain optical signalling"),
    (("voeikov", "воейков", "brizhik", "madl"), "water & coherent domains"),
    (("van wijk", "kobayashi"), "human UPE & measurement methodology"),
]
STRAND_BY_TOPIC = [
    ("skin protection and aging", "human UPE & methodology"),
    ("photosynthetic processes", "delayed luminescence & photosynthesis"),
    ("photodynamic therapy", "ROS / singlet-oxygen photon emission"),
    ("free radicals", "ROS / singlet-oxygen photon emission"),
]


def _strand_name(lab: dict) -> str:
    blob = " ".join(lab.get("top_topics", [])).lower()
    # ROS/singlet-oxygen is a topical strand even when a methodology author
    # (Van Wijk) tops it, so let that topic win before the author rules.
    if "photodynamic therapy" in blob or "free radicals" in blob:
        return "ROS / singlet-oxygen photon emission"
    auth = " ".join(lab.get("top_authors", [])[:4]).lower()
    for keys, name in STRAND_BY_AUTHOR:
        if any(k in auth for k in keys):
            return name
    for key, name in STRAND_BY_TOPIC:
        if key in blob:
            return name
    return lab.get("label", "")


def core_internal_structure() -> list[str]:
    """Promote the community-0 subdivision (subdivide.py) into a book subsection
    describing the biophoton core's real internal strands + the split-off wings."""
    p = C.EXPORTS / "community0_subcluster_labels.json"
    if not p.exists():
        return []
    labs = json.loads(p.read_text())
    core = sorted([(int(k), v) for k, v in labs.items() if v.get("is_core")],
                  key=lambda kv: kv[1]["n_seeds"], reverse=True)
    consc = [(int(k), v) for k, v in labs.items()
             if v.get("is_consciousness")]
    L = ["#### Inside the biophoton core — sub-strands (Leiden res 3.0)\n",
         "Re-clustering community 0 resolves the true UPE core into distinct "
         "research strands (the biofield/EEG/EMF/quantum-information literature "
         "splits off into its own sub-clusters):\n"]
    for sc, v in core:
        name = _strand_name(v)
        auth = ", ".join(v.get("top_authors", [])[:4])
        rep = (v.get("reps") or [""])[0]
        L.append(f"- **{name}** (sub {sc}: {v['n_works']} works, "
                 f"{v['n_seeds']} seeds) — {auth}." +
                 (f" _e.g. {rep}_" if rep else ""))
    if consc:
        sc, v = consc[0]
        L.append(f"\n**Split-off — consciousness/paranormal wing** (sub {sc}: "
                 f"{v['n_works']} works, {v['n_seeds']} seeds): "
                 f"{', '.join(v.get('top_authors', [])[:4])}. This is the "
                 f"reputationally-mixed strand the book should handle "
                 f"separately; researchers here are flagged "
                 f"`consciousness_adjacent=1` in researchers.csv.")
    L.append("")
    return L


def field_state(c) -> str:
    wc = pd.read_csv(C.EXPORTS / "work_communities.csv")
    works = pd.read_sql_query(
        "SELECT work_id, title, year, cited_by_count, is_seed FROM works", c)
    works = works.merge(wc[["work_id", "coupling_community"]], on="work_id",
                        how="left")
    labels = {d["community"]: d for d in load_communities()}

    wa = pd.read_sql_query(
        "SELECT wa.work_id, a.display_name, a.country, a.last_institution_id "
        "FROM work_authors wa JOIN authors a ON a.author_id=wa.author_id", c)

    # seed-anchored works = seeds + works that CITE a seed (forward direction —
    # papers building ON the field). We deliberately exclude works the seeds
    # merely reference (backward), which are foundational physics (Bell, quantum
    # coherence) pulled in as citations rather than biophoton papers themselves.
    seed_ids = set(works[works["is_seed"] == 1]["work_id"])
    edges = pd.read_sql_query(
        "SELECT src_work_id, dst_work_id FROM citation_edges", c)
    seed_prox = set(seed_ids)
    seed_prox |= set(edges[edges["dst_work_id"].isin(seed_ids)]["src_work_id"])
    inst = pd.read_sql_query(
        "SELECT inst_id, display_name, country FROM institutions", c).set_index(
        "inst_id")
    try:
        ao = pd.read_sql_query("SELECT * FROM author_openness", c)
        wo = pd.read_sql_query("SELECT * FROM work_openness", c)
    except Exception:
        ao, wo = pd.DataFrame(), pd.DataFrame()
    researchers = (pd.read_csv(C.EXPORTS / "researchers.csv")
                   if (C.EXPORTS / "researchers.csv").exists() else pd.DataFrame())

    L = []
    L.append("# The Biophoton / Ultra-Weak Photon Emission Field — State of the Field\n")
    L.append("_Book chapter-0 scaffold, auto-generated from the field map "
             "(OpenAlex, harvested 2026-07-19/20). Every claim below is backed "
             "by works in `fieldmap.sqlite`; counts are reproducible from the "
             "cache._\n")

    total = len(works)
    seeds = int((works["is_seed"] == 1).sum())
    L.append(f"## Overview\n")
    L.append(f"The map covers **{total:,} works** and "
             f"**{pd.read_sql_query('SELECT COUNT(*) n FROM authors', c)['n'][0]:,} "
             f"authors**, grown by 2-hop citation expansion from **{seeds} "
             f"resolved Cifra seed works**. Bibliographic-coupling community "
             f"detection (Leiden) separates the field into distinct "
             f"intellectual sub-fields; the sonoluminescence/cavitation physics "
             f"forms its **own** communities, confirming empirically that it is "
             f"an *adjacency* to — not part of — the biophoton core.\n")

    if not wo.empty:
        L.append(f"Field-wide openness: **{wo['is_oa'].mean()*100:.0f}%** of "
                 f"works are open access; **{int(wo['has_preprint'].sum())}** "
                 f"have a preprint; **{int(wo['open_signal'].sum())}** carry an "
                 f"open-data/code signal in their abstract.\n")

    # --- sub-fields ------------------------------------------------------
    L.append("## The sub-fields\n")
    for comm, title in SCOPE.items():
        info = labels.get(comm)
        if not info:
            continue
        grp = works[works["coupling_community"] == comm]
        ids = set(grp["work_id"])
        # seed-anchored subset of this community
        grp_anchor = grp[grp["work_id"].isin(seed_prox)]
        anchor_ids = set(grp_anchor["work_id"]) or ids
        countries = Counter(
            wa[wa["work_id"].isin(anchor_ids)]["country"].dropna())
        insts = Counter(
            wa[wa["work_id"].isin(anchor_ids)]["last_institution_id"].dropna())
        top_inst = []
        for iid, n in insts.most_common(4):
            if iid in inst.index:
                top_inst.append(f"{inst.loc[iid, 'display_name']} ({n})")
        # authors ranked by seed-anchored work count in this community
        anchor_authors = Counter(
            wa[wa["work_id"].isin(anchor_ids)]["display_name"].dropna())
        key_authors = [a for a, _ in anchor_authors.most_common(6)]
        # representative works = top-cited among seed-anchored works (drop magnets)
        rep_pool = grp_anchor if len(grp_anchor) else grp
        reps = (rep_pool[rep_pool["cited_by_count"] < CITATION_MAGNET]
                .sort_values("cited_by_count", ascending=False).head(4))
        mean_open = None
        if not ao.empty and not researchers.empty:
            rc = researchers[researchers["community"] == comm]
            if len(rc):
                mean_open = rc["openness"].mean()

        L.append(f"### {title}  (community {comm})")
        L.append(f"- **{len(grp):,} works**, {int((grp['is_seed']==1).sum())} "
                 f"seeds, median year {info.get('year_median')}, "
                 f"range {info.get('year_range')}.")
        L.append(f"- **Themes:** {', '.join(info.get('top_topics', [])[:5])}.")
        L.append(f"- **Key authors (seed-anchored):** "
                 f"{', '.join(key_authors)}.")
        if top_inst:
            L.append(f"- **Where it lives:** {'; '.join(top_inst)}.")
        if countries:
            cc = ', '.join(f"{k} ({v})" for k, v in countries.most_common(5))
            L.append(f"- **Geography (author affiliations):** {cc}.")
        if mean_open is not None:
            L.append(f"- **Mean author openness:** {mean_open:.2f}.")
        if len(reps):
            L.append("- **Representative works:**")
            for r in reps.itertuples():
                L.append(f"    - {str(r.title)[:100]} ({r.year}, "
                         f"{r.cited_by_count} cites)")
        L.append("")
        # promote the community-0 internal taxonomy right after the core block
        if comm == 0:
            L.extend(core_internal_structure())

    # --- timeline --------------------------------------------------------
    L.append("## Timeline of the field\n")
    yr = works.dropna(subset=["year"])
    by_decade = Counter((int(y)//5)*5 for y in yr["year"] if y and y > 1900)
    L.append("Works per 5-year bin (whole universe):\n")
    for d in sorted(by_decade):
        bar = "█" * max(1, by_decade[d] // 60)
        L.append(f"- {d}–{d+4}: {by_decade[d]:>5}  {bar}")
    L.append("")

    # --- open vs closed --------------------------------------------------
    if not researchers.empty and "openness" in researchers.columns:
        L.append("## The open-vs-closed analysis\n")
        core = researchers[researchers["community"] == 0]
        cand = core[core["n_works"] >= 3].dropna(subset=["openness"])
        top_open = cand.sort_values("openness", ascending=False).head(8)
        top_closed = cand.sort_values("openness").head(8)
        L.append("Within the biophoton core (community 0, researchers with ≥3 "
                 "in-universe works), the openness overlay separates who builds "
                 "the field in the open from who encloses it:\n")
        L.append("**Most open:**")
        for r in top_open.itertuples():
            L.append(f"- {str(r.display_name)[:30]} — openness "
                     f"{r.openness:.2f} (OA {r.oa_share:.0%}, preprint "
                     f"{r.preprint_rate:.0%})")
        L.append("\n**Least open:**")
        for r in top_closed.itertuples():
            L.append(f"- {str(r.display_name)[:30]} — openness "
                     f"{r.openness:.2f} (OA {r.oa_share:.0%})")
        L.append("")

    # --- gaps ------------------------------------------------------------
    L.append("## Gaps & whitespace\n")
    L.append("- **Author disambiguation:** OpenAlex splits some core authors "
             "(Van Wijk, Popp merged here; others flagged in "
             "`author_splits_flagged.json`) — a manual pass would sharpen "
             "centrality/ranking.")
    L.append("- **Full-text open-data signals:** open-data/code detection here "
             "is abstract-level; scanning OA full text would raise recall.")
    L.append("- **The consciousness-adjacent wing** (Persinger, Dotta, Tuszyński "
             "in community 0) is reputationally mixed and worth separating "
             "editorially in the book.\n")

    L.append("## Deliverables\n")
    L.append("- `fieldmap.sqlite` + parquet/CSV — the queryable database.")
    L.append("- `researchers.csv` — ranked outreach table (internal email column).")
    L.append("- `knowledge_map.html` — interactive researcher map.")
    L.append("- `*.graphml` — all four graphs for Gephi.")
    return "\n".join(L)


def knowledge_map(c) -> None:
    """Top researchers as an interactive coauthorship map (pyvis)."""
    from pyvis.network import Network
    if not (C.EXPORTS / "researchers.csv").exists():
        print("  (skip knowledge_map: researchers.csv missing)")
        return
    r = pd.read_csv(C.EXPORTS / "researchers.csv").head(250)
    ids = set(r["author_id"])
    ce = pd.read_sql_query(
        "SELECT author_a, author_b, weight FROM coauthor_edges", c)
    # map raw ids to canonical via researchers set: keep edges among top ids
    ce = ce[ce["author_a"].isin(ids) & ce["author_b"].isin(ids)]

    palette = ["#e6194B", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
               "#42d4f4", "#f032e6", "#bfef45", "#fabed4", "#469990"]
    net = Network(height="820px", width="100%", bgcolor="#111",
                  font_color="#eee", notebook=False)
    net.barnes_hut(gravity=-8000, spring_length=120)
    comm_ids = sorted(r["community"].dropna().unique())
    cmap = {cc: palette[i % len(palette)] for i, cc in enumerate(comm_ids)}

    for row in r.itertuples():
        size = 8 + 40 * (float(getattr(row, "eigenvector", 0) or 0))
        openv = float(getattr(row, "openness", 0) or 0)
        border = "#ffffff" if openv >= 0.5 else "#555555"
        title = (f"{row.display_name}\ncluster: {row.cluster}\n"
                 f"score {row.outreach_score:.3f} | openness {openv:.2f}\n"
                 f"seed-conn {row.seed_connectedness} | works {row.n_works}")
        net.add_node(row.author_id, label=str(row.display_name),
                     color={"background": cmap.get(row.community, "#999"),
                            "border": border},
                     size=size, borderWidth=3 if openv >= 0.5 else 1,
                     title=title)
    added = set(r["author_id"])
    for e in ce.itertuples():
        if e.author_a in added and e.author_b in added:
            net.add_edge(e.author_a, e.author_b,
                         value=float(e.weight), color="#333")
    out = C.OUTPUTS / "knowledge_map.html"
    net.write_html(str(out), notebook=False)
    print(f"  wrote {out} ({len(added)} nodes)")


def main() -> None:
    c = con()
    md = field_state(c)
    (C.OUTPUTS / "field_state.md").write_text(md)
    print(f"Wrote outputs/field_state.md ({len(md)} chars)")
    knowledge_map(c)
    c.close()
    with open(C.RUN_LOG, "a", encoding="utf-8") as f:
        f.write("\n## Stage H — synthesis\n\n- field_state.md + "
                "knowledge_map.html written\n")


if __name__ == "__main__":
    main()
