# Biophoton / UPE Knowledge Graph

A structured database and network analysis of the biophoton / ultra-weak photon
emission (UPE) / biological autochemiluminescence research field, seeded from
Michal Cifra's Zotero library and enriched via [OpenAlex](https://openalex.org),
with an open-science overlay.

Built for the [Open Science Foundation](https://opening.science) as the
evidence base for an open-source book on the state of the field.

**Snapshot 2026-07 · License [CC0 1.0](LICENSE) · DOI
[10.5281/zenodo.21466492](https://doi.org/10.5281/zenodo.21466492)**

## The map

[`biophoton-fieldmap/outputs/network_graph.html`](biophoton-fieldmap/outputs/network_graph.html)
is a self-contained interactive co-authorship network: the top 320 ranked
researchers, 1,094 co-authorship links, laid out as islands by Leiden sub-field.
No build step, no CDN, no server — download it and open it in any browser.

Nodes are sized by eigenvector centrality and can be coloured either by
sub-field or by the per-author openness score, which is where the open-vs-closed
structure of the field becomes visible. Hover for a researcher, click to pin,
search by name or institution, toggle sub-fields from the legend.

Two older views ship alongside it:
`Biophoton_Field_Map_Report.html` (the full narrative report) and
`knowledge_map.html` (the original pyvis graph, which needs a network
connection for its CDN assets).

## What the analysis found

- The field splits into a **biophoton/UPE core**, a distinct
  **ROS/redox/biochemiluminescence** wing, and a multi-part
  **sonoluminescence/cavitation physics** periphery.
- **Sonoluminescence is an adjacency, not the core.** It clusters separately
  under bibliographic coupling, which answers the field-boundary question
  empirically rather than by assumption.
- The openness overlay separates open from closed groups quantitatively.
  Field-wide open-access share is roughly 38%.

Written up in [`field_state.md`](biophoton-fieldmap/outputs/field_state.md) (the
book's chapter-0 scaffold) and
[`field_boundary_report.md`](biophoton-fieldmap/outputs/field_boundary_report.md).

## The literature corpus and knowledgebase

On top of the map sits a full-text layer: every open-access PDF the map can
reach, harvested politely (identified robot, per-host throttling, no
impersonation), text-extracted, and joined back to the map in one queryable
SQLite knowledgebase — **4,343 PDFs (63.5% of the field's OA output, 11.3 GB)**,
4,916 mined sentences in which the field states its own open problems.
The corpus itself is not redistributed; the tracked
[`literature/manifest.csv`](literature/manifest.csv) carries DOI, source URL
and sha256 for every work, so it is reconstructable and verifiable. Design,
schema and rebuild runbook: [`docs/LITERATURE_CORPUS.md`](docs/LITERATURE_CORPUS.md).

Headline synthesis:
[`open_research_questions.md`](biophoton-fieldmap/outputs/book_planning/open_research_questions.md)
— the field's seven major open questions in its own words, from mechanism
(UV emission unexplained) to the metrology hole (no absolute units, no
calibration chain, no inter-laboratory comparability) that the corpus shows
sits upstream of the mechanism, coherence, signalling and brain-UPE disputes
alike.

## Repository layout

| Path | What it holds |
|---|---|
| `biophoton-fieldmap/src/` | The pipeline, one module per stage |
| `biophoton-fieldmap/outputs/` | Reports, the interactive graph, the compact network JSON |
| `literature/` | The literature corpus: tracked index + manifests; PDFs and databases are local-only, rebuildable |
| `docs/` | Data dictionary, changelog, clustering strategy, literature-corpus documentation |
| `OpenAlex_Field_Map_Spec_for_ClaudeCode.md` | The original build spec |
| `cifra_seeds.csv` | The 263-entry seed table |

## Running the pipeline

```bash
python -m venv .venv && source .venv/bin/activate
pip install httpx tenacity pandas pyarrow rapidfuzz networkx python-igraph \
            leidenalg pyvis unidecode pymupdf tqdm
```

Then, from `biophoton-fieldmap/src/`:

```bash
python seed_resolve.py   # A: 263 seeds -> OpenAlex work ids (245 resolved)
python expand.py         # B: 2-hop citation expansion -> 18,355-work universe
python build_db.py       # C: normalize -> fieldmap.sqlite + parquet/CSV
python networks.py       # D: coauthorship/coupling/cocitation graphs + Leiden
python checkpoint.py     # Milestone-2 report (boundary answer + verification)
python subdivide.py      # split the UPE core at higher resolution
python openness.py       # E: per-work and per-author openness scoring
python contacts.py       # F: ORCID/institution routing (see data ethics below)
python rank.py           # G: composite outreach score
python synthesize.py     # H: field_state.md + knowledge_map.html
python build_network_json.py   # compact network for the interactive graph
python build_graph_html.py     # -> outputs/network_graph.html
```

`rank.py` must run after `subdivide.py`, and `build_graph_html.py` after
`build_network_json.py`. Every OpenAlex call is cached on disk keyed by entity
id, so all stages are idempotent and reruns are free. Every prune and cap is
recorded in [`run_log.md`](biophoton-fieldmap/run_log.md).

### Configuration

OpenAlex credentials and the polite-pool contact address are read from
environment variables, falling back to gitignored files in
`biophoton-fieldmap/`:

| Setting | Env var | File |
|---|---|---|
| API key | `OPENALEX_API_KEY` | `.openalex_key` |
| Contact address | `OPENALEX_MAILTO` | `.openalex_mailto` |

A free API key comes from [openalex.org/settings/api](https://openalex.org/settings/api).
Neither file is committed.

## Data ethics

Corresponding-author email addresses were collected from open-access PDFs the
researchers published themselves, for scholarly outreach. **They are internal to
OSF and are not in this repository or in the public dataset** — the harvest
cache, the working database and every researcher table that carries an email
column are gitignored, and `src/build_release.py` strips those columns and
scans for leaks before a release is cut.

The published data holds public identifiers only: names, ORCID, ROR-linked
institutions, scores. The full policy, including provenance and opt-out
handling, is in
[`NOTES_data_ethics.md`](biophoton-fieldmap/NOTES_data_ethics.md). To have your
record amended or removed, open an issue.

## Data release

This repository holds the code, the documents and the interactive graph. The
full dataset — SQLite databases, parquet/CSV exports, and the GraphML graphs for
Gephi — is deposited on Zenodo under
[10.5281/zenodo.21466492](https://doi.org/10.5281/zenodo.21466492) and can be
rebuilt locally with `python src/build_release.py`.

## Citing

Etzrodt, M. (2026). *Biophoton / Ultra-Weak Photon Emission Field Map* (1.0.0)
[Data set]. Zenodo. https://doi.org/10.5281/zenodo.21466493

See [`CITATION.cff`](CITATION.cff).
