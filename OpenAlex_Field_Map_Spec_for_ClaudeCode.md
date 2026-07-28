# Biophoton / UPE Field Map & Researcher Network — Claude Code Handoff Spec

**Prepared for:** Martin Etzrodt (OSI Director) · Open Science Foundation
**Purpose:** Build a structured database + network analysis of the biophoton / ultra-weak photon emission (UPE) / biological autochemiluminescence (BAL) research field, seeded from Michal Cifra's Zotero library, enriched via OpenAlex. First output feeds an **OSF open-source book on the current state of the field, with an open-science angle.**
**Prepared:** 2026-07-19. Run target: a Claude Code session (this needs live programmatic OpenAlex access, which the Cowork web-fetch sandbox is robots-blocked from).

---

## 0. Scope decisions (locked with Martin)

| Decision | Choice |
|---|---|
| Field boundary | **Harvest everything, draw the boundary analytically from the map** — do not pre-filter clusters; let community detection + topic analysis reveal where the biophoton core ends and adjacencies (sonoluminescence physics, general ROS chemistry) begin. |
| Citation expansion | **Broad: 2 hops**, backward + forward, with density-based pruning between hops. |
| Contact data | ORCID + institutional pages **and** corresponding-author emails extracted from open-access PDFs (with the GDPR/etiquette handling in §7). |
| Execution | Claude Code session; this spec + `cifra_seeds.csv` are the inputs. |

The **open-science overlay (§6) is the differentiator** — this is not a generic bibliometric review; every work and author is scored on openness so the book can tell the story of who builds this field in the open vs who encloses it.

---

## 1. Inputs provided

- `BAL_biophotons_Cifra_Zotero.bib` — 263 entries, Cifra group (Zotero group 2260466), exported 2026-07-19.
- `cifra_seeds.csv` — pre-parsed seed table: `bib_key, entry_type, year, first_author, title, venue, doi`. 203 rows have a DOI (direct OpenAlex anchor); 60 need fuzzy title+year matching (these include core biophoton papers — Popp, Van Wijk, Cifra, Kobayashi, Salari, Scholkmann — so do NOT drop them).

### Seed corpus shape (from parse — informs expectations)
- Years 1923–2025, peak 2010s (88), 2000s (62), 2020s (48 so far).
- 760 unique author name-strings (pre-disambiguation).
- Visible communities in the seed: **(a)** biophoton/UPE core (Cifra, Popp, Van Wijk ×2, Kobayashi, Pospíšil, Poplová, Scholkmann, Fels, Salari); **(b)** delayed luminescence / coherence (Musumeci, Scordino, Tudisco, Grasso — Catania); **(c)** ROS/biochemiluminescence (Voeikov, Nowak/Sarniak Fe–EGTA–H₂O₂, Maillard, humic acids); **(d)** human/consciousness-adjacent UPE (Persinger, Dotta, Caswell — reputationally mixed, tag it); **(e)** sonoluminescence/acoustic cavitation physics (Yasui, Ashokkumar, Lee, Grieser, Brenner, Nikitenko — likely an adjacency, let the map confirm).

---

## 2. Architecture & repo layout

```
biophoton-fieldmap/
  data/
    raw/            # cifra_seeds.csv, the .bib
    cache/          # one JSON per OpenAlex entity (id-keyed) — resumable
    db/             # fieldmap.sqlite
    exports/        # csv/parquet, graphml, gexf
  src/
    config.py       # MAILTO, thresholds, caps
    openalex.py     # thin client: polite pool, cursor paging, retry, disk cache
    seed_resolve.py # csv/bib -> OpenAlex work ids (doi + fuzzy title match)
    expand.py       # 2-hop backward+forward with pruning
    build_db.py     # normalize entities -> sqlite tables
    networks.py     # coauthorship / co-citation / bibliographic coupling graphs + Leiden
    openness.py     # per-work + per-author openness scoring
    contacts.py     # ORCID/institution + OA-PDF email extraction
    rank.py         # composite outreach score
    synthesize.py   # field-overview markdown + cluster summaries
  outputs/
    knowledge_map.html      # interactive force graph (pyvis or d3)
    researchers.csv         # ranked outreach table
    field_state.md          # book chapter-0 scaffold
  run.py            # orchestrates stages, idempotent/resumable
  README.md
```

**Principles:** every OpenAlex call cached to disk keyed by entity id, so reruns are free and the harvest is resumable. All stages idempotent. Log every prune/cap so nothing is silently dropped.

---

## 3. Environment

```bash
python -m venv .venv && source .venv/bin/activate
pip install httpx tenacity pandas pyarrow rapidfuzz networkx python-igraph leidenalg \
            pyvis unidecode pymupdf tqdm
```

- **OpenAlex polite pool:** add `mailto=<Martin's email>` to every request (set in `config.py`). No API key needed. Limits: ~10 req/s, 100k/day — cursor-paginate, cache aggressively, `time.sleep` politely, exponential backoff via `tenacity`.
- Set `MAILTO`, and a global `HARD_CAP_WORKS` (default 40_000) and prune thresholds (below) in config so the 2-hop harvest can't runaway.

---

## 4. Pipeline

### Stage A — Seed resolution (`seed_resolve.py`)
1. DOI rows → `GET /works?filter=doi:<doi>&mailto=...` (batch up to 50 DOIs with `doi:a|b|c`).
2. No-DOI rows → `GET /works?filter=title.search:<title>&mailto=...`, then confirm with `rapidfuzz` token_set_ratio ≥ 90 against title AND year within ±1. Log any unmatched for manual review (expect a few patents/theses/grey-lit that aren't in OpenAlex).
3. Output `seed_works` table with OpenAlex work IDs. Target: ≥240/263 resolved.

**Fields to `select` on works** (keep payloads small):
`id,doi,title,publication_year,type,cited_by_count,authorships,primary_topic,topics,concepts,referenced_works,related_works,open_access,primary_location,locations,corresponding_author_ids,language`

### Stage B — 2-hop expansion (`expand.py`)
- **Hop 1 backward:** union of every seed's `referenced_works`.
- **Hop 1 forward:** for each seed, `GET /works?filter=cites:<workid>` (cursor-paged). For very-highly-cited seeds (e.g. Brenner sonoluminescence RMP), cap forward citations per seed (e.g. top 500 by `cited_by_count`) and log the cap.
- **Prune to hop-1 core:** keep a candidate work iff it links to **≥2 seeds** (cited by ≥2 seeds, OR cites ≥2 seeds, OR appears in ≥2 seeds' `related_works`). This is the coupling/co-citation threshold that keeps the biophoton core and drops one-off physics tangents.
- **Hop 2:** expand backward+forward **only from the pruned hop-1 core**, prune again with a **≥3-link** threshold (stricter, since hop-2 is noisier). Respect `HARD_CAP_WORKS`; if hit, keep highest link-density first and log what was dropped.
- Output: `works` universe (seeds + surviving hop-1 + hop-2), plus `citation_edges`.

### Stage C — Normalize to DB (`build_db.py`) — schema
- `works(work_id PK, doi, title, year, type, cited_by_count, oa_status, is_oa, oa_url, lang, is_seed, hop)`
- `authors(author_id PK, display_name, orcid, works_count, cited_by_count, mean_citedness_2y, last_institution_id, country)`
- `institutions(inst_id PK, display_name, type, country, ror)`
- `work_authors(work_id, author_id, position, is_corresponding, raw_affiliation_string)`
- `topics(work_id, topic_id, topic_name, domain, field, subfield, score)` (OpenAlex `topics` are the current taxonomy; also keep legacy `concepts` for continuity)
- `citation_edges(src_work_id, dst_work_id)` (src cites dst)
- `coauthor_edges(author_a, author_b, weight)` (materialized in Stage D)
- Emit parquet + CSV exports alongside SQLite.

### Stage D — Networks (`networks.py`)
Build with igraph; cluster with `leidenalg` (RBConfigurationVertexPartition, resolution tunable):
1. **Co-authorship** (author nodes, shared-work edges) → research groups/labs. This + institution roll-up = "who works with whom, where."
2. **Bibliographic coupling** (work–work, shared references) and **co-citation** (work–work, co-cited by later work) → **intellectual sub-fields**. These two are what draw the field boundary Martin asked to derive from the map. Report the cluster membership of the sonoluminescence set explicitly — that answers the boundary question empirically.
3. **Topic co-occurrence** → thematic map; label each Leiden community by its top topics + top authors + representative papers.
4. **Temporal & geographic layers:** cluster size over time (rising/declining sub-topics); institution/country network (where the field lives, where the open groups are).
Export GraphML/GEXF (for Gephi) + node/edge CSVs. Compute per-author centrality (degree, betweenness, eigenvector) for ranking.

### Stage E — Openness overlay (`openness.py`) — see §6
### Stage F — Contacts (`contacts.py`) — see §7
### Stage G — Ranking (`rank.py`) — see §8
### Stage H — Synthesis (`synthesize.py`) — see §9

---

## 6. Open-science overlay (the OSF differentiator)

Per **work**: `oa_status` (gold/green/hybrid/bronze/closed), `is_oa`, has-preprint (any location with `version=submittedVersion` or a preprint-server host), and — where derivable — open-data / open-code / open-protocol / open-hardware mentions (scan abstract + OA full text for repository DOIs, github.com, zenodo, osf.io, protocols.io, hardware repos).

Per **author**, an **Openness Score ∈ [0,1]** = weighted mean of:
- OA share of their works in the field universe (weight 0.4)
- preprint adoption rate (0.2)
- open-data/code/hardware signal rate (0.25)
- presence on open infrastructure (ORCID populated, ROR-linked, OSF/Zenodo deposits) (0.15)

Keep the components, not just the composite — the book will want to show the breakdown. This operationalizes the known tension (Cifra critical-but-open vs the Calgary/Simon-Oblak group closed/gatekeeping): expect the overlay to separate them quantitatively, which is a headline the book can use.

---

## 7. Contact extraction (`contacts.py`)

1. **Clean routing (always):** ORCID (from OpenAlex author object) → ORCID public record; `last_known_institution` + ROR → institutional profile URL. Store these first.
2. **Email from OA PDFs (Martin approved):** for each target researcher's recent corresponding-authored OA works, fetch `open_access.oa_url` / best OA `pdf_url` (Unpaywall via OpenAlex location is fine), extract text with PyMuPDF, regex emails near "corresponding author" / the author's surname, validate domain against the institution. Store `email, source_work_doi, extraction_confidence, retrieved_date`.
3. **Do not** brute-force or guess emails; only use ones a researcher published themselves in their own paper.
4. **GDPR / etiquette:** this is academic contact data the researchers self-published; processing basis is legitimate interest for scholarly outreach. Keep provenance per email, keep the dataset internal to OSF, honor opt-outs, and don't publish the email column in the open book/dataset. Add a `NOTES_data_ethics.md` recording this.

---

## 8. Composite outreach ranking (`rank.py`)

Per researcher, `outreach_score` (normalize each term to [0,1] across the universe):
```
0.30 * seed_connectedness   # authored/cited-by seed works; proximity to Cifra core
0.20 * field_centrality     # eigenvector centrality in coauthorship + coupling graphs
0.20 * recent_activity      # works in last 5y in-universe (the "active researcher" ask)
0.15 * topical_fit          # share of their in-universe works in core biophoton/UPE topics
0.15 * openness_score       # §6 — OSF cares who is open
```
Output `researchers.csv`: rank, name, ORCID, institution, country, cluster label, top topics, in-universe works, recent works, centrality, openness (+ components), contact route(s), email(+provenance). Provide sortable/filterable views (e.g. "top 50 overall", "top open researchers", "rising since 2022", "per sub-field").

---

## 9. Deliverables (`synthesize.py` + outputs/)

1. **`fieldmap.sqlite`** + parquet/CSV exports — the queryable database.
2. **`knowledge_map.html`** — interactive force-directed graph (pyvis or self-contained d3), nodes colored by Leiden community, sized by centrality, openness on a secondary channel; filter by sub-field/year. Also GraphML/GEXF for Gephi.
3. **`researchers.csv`** — the ranked, contactable outreach table (§8).
4. **`field_state.md`** — the book's chapter-0 scaffold: narrative of the sub-fields (auto-labeled from clusters), key labs & geography, timeline of the field, the open-vs-closed analysis, and identified gaps/whitespace. Each claim links to supporting works in the DB.

---

## 10. Verification (build in, don't skip)

- **Seed coverage:** assert ≥240/263 seeds resolved; dump unmatched with reasons.
- **Boundary sanity:** confirm the sonoluminescence set lands in its own community distinct from the UPE core (validates the coupling clustering; if it doesn't, the graph is under-connected — revisit thresholds).
- **Known-author spot checks:** Cifra, Van Wijk, Kobayashi, Pospíšil, Popp, Salari must appear with sane institutions, ORCIDs, and high seed-connectedness. Manually eyeball 10 disambiguated authors for merge/split errors (OpenAlex author disambiguation is good but not perfect — flag suspicious splits).
- **Openness face-validity:** verify the overlay reproduces at least one known case (open vs closed group) correctly.
- **Reproducibility:** pin OpenAlex snapshot date; the cache makes the run fully reproducible; record counts at every prune in `run_log.md`.

---

## 11. Suggested run order / milestones

1. Stages A–C → **DB of the resolved + expanded universe** (checkpoint: how big did it get, what's the boundary shape).
2. Stage D → **networks + clusters** (checkpoint: does the field boundary make sense — this is the analytical answer to the scope question).
3. Stages E–G → **openness + contacts + ranking** → `researchers.csv`.
4. Stage H → **`field_state.md` + `knowledge_map.html`** → hand back to Martin for the book.

Checkpoint with Martin after milestone 2 (the cluster map) before spending effort on full contact extraction — the map may reshape which clusters are in-scope for outreach.
```
```
