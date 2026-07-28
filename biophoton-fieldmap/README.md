# Biophoton / UPE Field Map

Structured database + network analysis of the biophoton / ultra-weak photon
emission (UPE) research field, seeded from Michal Cifra's Zotero library and
enriched via OpenAlex, with an open-science overlay. Feeds an OSF open-source
book on the state of the field.

## Pipeline (run order)

```bash
source .venv/bin/activate
cd src
python seed_resolve.py   # A: 263 seeds -> OpenAlex work ids (245 resolved)
python expand.py         # B: 2-hop citation expansion -> 18,355-work universe
python build_db.py       # C: normalize -> fieldmap.sqlite + parquet/CSV
python networks.py       # D: coauthorship/coupling/cocitation/topic graphs + Leiden
python checkpoint.py     # Milestone-2 report (boundary answer + verification)
python subdivide.py      # split community 0 at higher res -> UPE-core sub-strands
python openness.py       # E: per-work + per-author openness scoring
python contacts.py       # F: ORCID/inst routing + bounded email-from-OA-PDF
python rank.py           # G: composite outreach score -> researchers.csv
python synthesize.py     # H: field_state.md + knowledge_map.html

# rank.py must run after subdivide.py to get the consciousness_adjacent flag +
# core_strand column; synthesize.py promotes the sub-strands into field_state.md.
```

Every OpenAlex call is cached under `data/cache/` (keyed by entity id), so every
stage is idempotent and reruns are free. Requires a free OpenAlex API key in
`.openalex_key` (or `OPENALEX_API_KEY`) — see `src/config.py`.

## Key deliverables

- `data/db/fieldmap.sqlite` — queryable DB (works, authors, institutions,
  work_authors, topics, citation/coauthor edges, work/author openness).
- `outputs/field_state.md` — book chapter-0 scaffold.
- `outputs/field_boundary_report.md` — Milestone-2 cluster map + verification.
- `outputs/knowledge_map.html` — interactive researcher map (open in a browser).
- `data/exports/researchers.csv` — ranked outreach table (+ core/open/rising views).
- `data/exports/*.graphml` — four graphs for Gephi.
- `run_log.md` — every prune/cap/count. `MILESTONE2_DECISIONS.md` — locked decisions.
- `NOTES_data_ethics.md` — contact-data handling (email column is INTERNAL).

## Headline findings

- The field splits (Leiden over bibliographic coupling) into a **biophoton/UPE
  core** (community 0), a distinct **ROS/redox/biochemiluminescence** wing (3),
  and a multi-part **sonoluminescence/cavitation physics** periphery (1,2,4,6).
- **Sonoluminescence is an adjacency, not the core** — it clusters separately,
  answering the field-boundary question empirically.
- Openness overlay separates open vs closed groups quantitatively (see
  field_state.md); field-wide OA share ≈ 38%.
