# Data dictionary

## fieldmap.sqlite

- **works**(work_id, doi, title, year, type, cited_by_count, oa_status, is_oa,
  oa_url, lang, is_seed, hop)
- **authors**(author_id, display_name, orcid, works_count, cited_by_count,
  mean_citedness_2y, last_institution_id, country)
- **institutions**(inst_id, display_name, type, country, ror)
- **work_authors**(work_id, author_id, position, is_corresponding,
  raw_affiliation_string)
- **topics**(work_id, topic_id, topic_name, domain, field, subfield, score)
- **citation_edges**(src_work_id, dst_work_id): src cites dst (within universe)
- **coauthor_edges**(author_a, author_b, weight)
- **work_openness**(work_id, oa_status, is_oa, has_preprint, open_signal, signal_terms)
- **author_openness**(author_id, n_works, oa_share, preprint_rate,
  open_signal_rate, infra_score, openness)

## paper_index.sqlite

- **papers**(rank, work_id, doi, title, authors, year, type, cited_by_count,
  link_count, primary_topic, core_topic, oa_status, is_oa, is_seed, hop,
  has_preprint, open_signal, paper_rank_score, abstract_inverted_index,
  openalex_url, link). `rank` is the composite paper-importance order.
  `abstract_inverted_index` is a JSON map of word to positions.
- **papers_fts**: contentless FTS5 over title/authors/abstract. Query with
  `SELECT rowid FROM papers_fts WHERE papers_fts MATCH '...'` then join `papers`
  on rowid. No source text is stored in the index.

## researchers*.csv

rank, author_id, display_name, orcid, institution, country, community, cluster,
core_strand, consciousness_adjacent, n_works, recent_works, seed_connectedness,
eigenvector, topical_fit, openness (+ components), cited_by_count,
outreach_score. Email columns are removed from this public release.

## Community codes (coupling)

0 Biophoton / UPE core; 3 ROS / redox / biochemiluminescence; 1 Sonochemistry /
cavitation; 2 Bubble and fluid physics; 4 Sonoluminescence physics; 6
Nanobubbles. Others are smaller adjacencies.
