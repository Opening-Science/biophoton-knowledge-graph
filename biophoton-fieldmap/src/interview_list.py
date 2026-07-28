"""Build an author / interview shortlist organized BY SUB-FIELD (the six
coupling communities), not by book chapter.

Reads researchers.csv, selects the top researchers per sub-field (excluding the
consciousness-adjacent wing, which is listed separately), and writes a markdown
list with a plain table per sub-field: researcher, institution, country,
openness, ORCID. Public routing only. Corresponding-author emails stay in the
internal contacts dataset and are reported only as an aggregate count.
"""
from __future__ import annotations

import pandas as pd

import config as C

# sub-field community -> (heading, one-line description, how many to list)
SUBFIELDS = [
    (0, "Biophoton / UPE core",
     "The measurement and theory core of ultra-weak photon emission.", 12),
    (3, "ROS / redox / biochemiluminescence",
     "Reactive-oxygen and redox chemistry that produces low-level light.", 10),
    (1, "Sonochemistry / acoustic cavitation",
     "Cavitation chemistry and advanced oxidation. Adjacency to the core.", 8),
    (2, "Bubble and fluid physics",
     "Bubble dynamics and multiphase flow. Adjacency to the core.", 7),
    (4, "Sonoluminescence physics",
     "Single-bubble sonoluminescence and cavitation physics. Adjacency.", 8),
    (6, "Nanobubbles",
     "Nanobubble and microbubble technology. Adjacency to the core.", 6),
]


def orcid_id(v) -> str:
    if pd.isna(v) or not str(v).strip():
        return ""
    return str(v).replace("https://orcid.org/", "")


def row_line(r) -> list[str]:
    inst = str(r.institution) if pd.notna(r.institution) else ""
    strand = str(getattr(r, "core_strand", "") or "")
    name = str(r.display_name)
    return [name, inst[:34], str(r.country) if pd.notna(r.country) else "",
            f"{float(r.openness or 0):.2f}", orcid_id(r.orcid), strand]


def main():
    r = pd.read_csv(C.EXPORTS / "researchers.csv")
    has_email = ("email" in r.columns)

    L = ["# Author and Interview List by Sub-field\n"]
    L.append("Recommended researchers to cite and interview for the OSF "
             "biophoton book, grouped by the six intellectual sub-fields the "
             "map detects. Within each sub-field, researchers are ordered by "
             "composite outreach score (proximity to the seed core, centrality, "
             "recent activity, topical fit, openness). Contact routing is public: "
             "ORCID and institution are listed for all. Corresponding-author "
             "emails are held in the internal contacts dataset and are reported "
             "here only as a count.\n")

    for comm, name, desc, n in SUBFIELDS:
        sub = r[(r["community"] == comm) &
                (r.get("consciousness_adjacent", 0) != 1)].head(n)
        if sub.empty:
            continue
        n_email = int((sub["email"].fillna("") != "").sum()) if has_email else 0
        L.append(f"## {name}\n")
        L.append(f"{desc}\n")
        # table
        cols = "| Researcher | Institution | Ctry | Open | ORCID |"
        sep = "|---|---|---|---|---|"
        L.append(cols)
        L.append(sep)
        for x in sub.itertuples():
            nm, inst, co, op, orc, strand = row_line(x)
            L.append(f"| {nm} | {inst} | {co} | {op} | {orc} |")
        L.append("")
        route = (f"Contact routing: ORCID and institution for all listed. "
                 f"Corresponding-author emails on file for {n_email} of these "
                 f"in the internal contacts dataset.")
        L.append(route + "\n")

    # consciousness-adjacent, listed separately per editorial guidance
    ca = r[(r.get("consciousness_adjacent", 0) == 1)].head(8)
    if not ca.empty:
        L.append("## Consciousness-adjacent (treat separately)\n")
        L.append("These researchers cite into the field and share seed papers, "
                 "but the map places them in a distinct sub-cluster. List them "
                 "for the critical treatment, not the measurement chapters.\n")
        L.append("| Researcher | Institution | Ctry | Open | ORCID |")
        L.append("|---|---|---|---|---|")
        for x in ca.itertuples():
            nm, inst, co, op, orc, strand = row_line(x)
            L.append(f"| {nm} | {inst} | {co} | {op} | {orc} |")
        L.append("")

    out = C.OUTPUTS / "interview_list.md"
    out.write_text("\n".join(L))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
