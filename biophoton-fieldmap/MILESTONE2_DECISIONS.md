# Milestone 2 checkpoint — decisions (2026-07-20)

Status: **paused at Milestone 2 for Martin's review.** Stages A–D complete;
Milestone 3 (openness + contacts + ranking) and Milestone 4 (synthesis) not started.

## Decisions locked with Martin at this checkpoint

1. **Outreach scope for the researcher ranking table (Stage G):**
   include the biophoton **core + ROS/redox wing + sonoluminescence/cavitation**.
   Concretely, bibliographic-coupling communities **0** (UPE/biophoton core),
   **3** (ROS/oxidative-stress/biochemiluminescence), and the physics adjacency
   communities **1, 2, 4, 6** (sonochemistry, bubble/fluid physics,
   sonoluminescence, nanobubbles). Martin explicitly wants the physics
   adjacency people in the outreach table, not just the core. Only the tiny
   fragment communities (5 bioelectricity, 7/8/9 singletons) are out of scope.

## Carry-forward fixes to apply in Milestone 3

- **Author disambiguation merges:** OpenAlex split **Van Wijk** into 4 records
  (Roeland / Eduard / Eduard P.A. / Eduard P A) and **Popp** into 2
  (F. A. Popp / Fritz-Albert Popp). Merge these before computing
  seed-connectedness / centrality / ranking so their influence isn't diluted.
- **Representative-paper selection:** filter citation-magnet outliers (e.g.
  "Hallmarks of Cancer", 66k cites in community 0) when picking representative
  works for the book; rank reps by in-topic relevance, not raw cited_by_count.

## Where the boundary landed (the analytical answer)

Sonoluminescence seed works → coupling community 4 (34/52); UPE core →
community 0. Distinct communities → sonoluminescence is an adjacency, confirmed
empirically. See `outputs/field_boundary_report.md`.
