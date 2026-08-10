# Changelog

## 1.1.0 (literature corpus, knowledgebase, clustering v2)

- **Literature corpus** (stages I–L): polite harvest of the universe's
  open-access PDFs — 3,966 of 6,842 OA works retrieved (58%, 10.2 GB),
  no browser impersonation; tracked manifest with DOI + sha256 + outcome
  per work. Full-text extraction (3,972 texts), 4,481 mined open-problem
  statements with page provenance, and a joined knowledgebase
  (works × authors × clustering × full text × FTS5).
  See `docs/LITERATURE_CORPUS.md`.
- **Book planning**: `outputs/book_planning/open_research_questions.md` —
  the field's seven major open questions in its own words, quote-anchored;
  plus the themed statement corpus behind it.
- **Clustering v2**: fractional-counting bibliographic coupling + CPM with
  stability analysis across Leiden reruns (ARI 0.814 ± 0.061); comparison
  in `outputs/recluster_comparison.md`, method in
  `docs/CLUSTERING_STRATEGY.md`. Original coupling numbering remains the
  reference frame; v2 ships alongside it.

## 1.0.0 (initial public release)

- First open release of the biophoton / UPE field map.
- 18,355 works, 39,312 authors, sub-field clustering, openness overlay.
- Abstracts shipped as inverted index. Contact emails excluded.
- License: CC0 1.0.
