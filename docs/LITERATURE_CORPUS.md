# Literature corpus and knowledgebase

The field map (18,355 works, 39k authors, clustered and openness-scored)
answers *who and what* the biophoton/UPE field is. This layer answers *what
the field's own texts say*: every open-access paper the map can reach,
downloaded, text-extracted, joined back to the map in one queryable
database, and mined for the field's self-declared open problems.

Built 2026-08-10. All stages are idempotent and resumable; rebuild with the
runbook at the end.

## What exists

| Artifact | Size | Tracked in git |
|---|---|---|
| `literature/papers/` — harvested OA PDFs, `<year>_<Author>_<OpenAlexID>.pdf` | 3,966 files, 10.2 GB | no (rebuildable) |
| `literature/books/`, `literature/curated/` — hand-collected material | 6 items | no |
| `literature/manifest.csv` — every OA work: outcome, DOI, sha256, source URL, failure reason | 6,842 rows | **yes** |
| `literature/curated.csv` — hand-collected items + corpus cross-reference | | **yes** |
| `literature/INDEX.md` — human-readable corpus index | | **yes** |
| `literature/fulltext.sqlite` — extracted text + mined statements | 3,972 texts, 0.43 GB | no |
| `literature/knowledgebase.sqlite` — everything joined (see schema below) | 0.51 GB | no |
| `biophoton-fieldmap/outputs/book_planning/` — analysis outputs | | partly (see below) |

Coverage: **3,966 of 6,842 open-access works (58%)**; with the universe
only ~37% OA, the corpus holds full text for **~22% of the entire mapped
field**, spanning 1897–2026. The 2,876 OA works that could not be fetched
are recorded per-work in the manifest with the HTTP reason — nearly all are
publishers that refuse any client identifying itself as a robot (Wiley,
Elsevier, ACS, OUP, SAGE, MDPI's rate limiter, …). See "Politeness policy".

## Pipeline (stages I–L, after the field map's A–H)

| Stage | Script (`biophoton-fieldmap/src/`) | Output |
|---|---|---|
| I. Harvest | `harvest_oa_pdfs.py` | `literature/papers/`, `manifest.csv`, `harvest_log.jsonl` |
| I½. Consolidate | `consolidate_literature.py` | `books/`, `curated/`, `curated.csv`, `INDEX.md` |
| J. Extract | `extract_fulltext.py` | `fulltext.sqlite` (text, quality flags, mined statements) |
| K. Knowledgebase | `build_knowledgebase.py` | `knowledgebase.sqlite` |
| L. Book planning | `book_planning.py` | `outputs/book_planning/*.md` |

### Stage I — harvest design

PDF resolution is layered, cheapest first: (1) direct `pdf_url`s already in
the cached OpenAlex records; (2) host-specific rewrites that turn landing
pages into files (arXiv `abs→pdf`, PMC → Europe PMC's render endpoint,
Springer `article→content/pdf`, PLOS printable, Frontiers `/pdf`, bioRxiv
`.full.pdf`, OSF `/download`, HAL `/document`, J-STAGE `_pdf`, …); (3) the
landing page itself, fetched and mined for its `citation_pdf_url` meta tag
(the standard way repositories advertise their files) with same-host
`.pdf` hrefs as fallback; (4) Unpaywall by DOI, cached, which resolves the
~1,450 works whose only OA URL is a bare `doi.org` redirect.

Notable empirical findings encoded in the resolver: NCBI's own PMC PDF
endpoints serve an interstitial to non-browser clients and the documented
`oa.fcgi` package links 404, so **Europe PMC's `?pdf=render` endpoint is
the only reliable robot route to PMC full text**; its 403/500s are
per-article ("not free here"), not throttling, and are exempted from the
circuit breaker.

**Politeness policy.** Requests are serialised per host with per-host
minimum intervals (arXiv 3 s as they request), a User-Agent that names the
project and carries a contact address, exponential backoff on 429/503, and
a circuit breaker that puts a host on a timed cooldown after repeated
refusals. **No browser impersonation is used** — a publisher that refuses
an identified robot is recorded, not evaded. That decision costs roughly a
fifth of the OA corpus and is deliberate: the manifest rows (DOI + reason)
are exactly what an institutional-access pass or interlibrary request
needs.

Every attempt is journaled in `harvest_log.jsonl`, so reruns skip what is
on disk and `--retry-failed` re-attempts soft failures only.

### Stage J — extraction design

PyMuPDF text per page. Two things are computed here because they need page
structure that is discarded afterwards: **quality flags** (no-text-layer /
mostly-scanned / references-heavy — 27 of 3,972 texts lack a text layer)
and **statement mining** — sentences matching high-precision markers for
open questions, future work, limitations, controversies and measurement
gaps, each stored with its page number. Metrology vocabulary ("detection
limit", "dark count", …) only counts as a gap statement when the sentence
also carries problem language, so an instrument spec is not a finding.
4,481 statements were mined.

### Stage K — the knowledgebase

`literature/knowledgebase.sqlite`:

- **works** — one row per universe work: metadata, rank score, abstract,
  both clusterings (`community` = original coupling numbering; and, where
  present, `community_v2` + per-node `stability` from the CPM re-clustering),
  core sub-strand, full-text status/quality.
- **authors** — canonical (merged) authors with openness score, institution,
  country, in-universe activity span (`first_year`/`last_year`).
- **work_authors** — link table with corresponding-author flag.
- **statements** — the mined sentences: work_id, page, kind, sentence.
- **chapter_map** — the draft book-chapter structure as data (chapter →
  anchor community/strand), so chapter-level questions are SQL joins.
- **works_fts** — FTS5 (porter) over title + abstract + full body text.

Example queries:

```sql
-- Full-text search across 3,967 papers, ranked by the field-map score
SELECT w.work_id, w.title, w.year
FROM works_fts f JOIN works w ON w.work_id = f.work_id
WHERE works_fts MATCH 'traceab* OR "absolute calibration"'
ORDER BY w.paper_rank_score DESC LIMIT 20;

-- Active authors in the neural-UPE strand with held full text
SELECT a.display_name, COUNT(*) n, MAX(w.year) latest
FROM works w JOIN work_authors wa USING(work_id)
             JOIN authors a USING(author_id)
WHERE w.core_strand = 15 AND w.has_fulltext = 1 AND a.last_year >= 2022
GROUP BY a.author_id ORDER BY n DESC;

-- What the field says is unsolved about coherence, with provenance
SELECT s.sentence, w.title, w.year, s.page
FROM statements s JOIN works w USING(work_id)
WHERE s.kind = 'open_question' AND s.sentence LIKE '%coheren%'
ORDER BY w.paper_rank_score DESC;
```

### Stage L — book-planning outputs

Published in `biophoton-fieldmap/outputs/book_planning/`:

- **`open_research_questions.md`** — seven major open questions the corpus
  itself states, each anchored in verbatim quotes with work id, page and
  DOI. Headline: the field's mechanism, coherence, signalling and brain-UPE
  disputes all bottleneck on the same missing layer — calibration, absolute
  units, and inter-laboratory comparability.
- **`open_question_statements.md`** — the ranked, themed statement corpus
  (274 statements) behind it.

Two further planning documents (per-chapter evidence tables and the
interview-slate refinement) contain candid per-person assessments and are
kept local by editorial decision; the scripts that generate them are
public, so any clone of the data can regenerate them.

## Rebuild runbook

```bash
cd biophoton-fieldmap && source .venv/bin/activate && cd src
python harvest_oa_pdfs.py              # hours; resumable; --retry-failed later
python consolidate_literature.py       # needs .literature_sources.json for
                                       # hand-collected items; skips otherwise
python extract_fulltext.py             # incremental; --rebuild after mining changes
python build_knowledgebase.py
python book_planning.py
```

Requires the field-map pipeline (stages A–H) to have run first, since the
harvest reads `works.parquet`, the clustering exports and the OpenAlex
cache. Hand-collected sources are declared in a gitignored
`.literature_sources.json` at the repo root (machine-local paths).

## Licence note

The corpus PDFs are open access at their sources but carry heterogeneous
licences, so the files themselves are not redistributed here. The tracked
manifest carries DOI, source URL, sha256 **and the per-work licence** (from
OpenAlex): of the 3,966 PDFs on disk, **2,378 (60%) are CC-licensed or
public domain and could lawfully be re-hosted** (1,724 CC-BY, 413
CC-BY-NC-ND, 141 CC-BY-NC, …); the rest are free-to-read at source only.
Any hosting decision can therefore be made per file with
`manifest.csv:license`. The corpus is reconstructable and verifiable
without redistribution.
