# Why the cluster descriptions read badly, and how to fix them

_Written 2026-08-09 against the OpenAlex harvest of 2026-07-19/20._

The Milestone-2 checkpoint describes bibliographic-coupling community 0 — the
"UPE / biophoton core" — by its most-cited members:

> Hallmarks of Cancer: The Next Generation (66,806); Quantum Mechanical Continuum
> Solvation Models (16,599); Calcium's Role in Mechanotransduction during Muscle
> Development (14,545); On the Einstein Podolsky Rosen paradox (12,270); …

Not one is an ultraweak-photon-emission paper and not one is a seed. This
document establishes where that came from, why it happened, what it does and
does not invalidate, and what to change.

---

## 1. Provenance

Yes — it is the Leiden work, and it reproduces exactly.

| step | file | what it does |
|---|---|---|
| build the coupling graph | [`src/networks.py`](../biophoton-fieldmap/src/networks.py) `build_coupling()` | link two works by the raw count of references they share; keep every pair at weight ≥ 2 |
| partition it | same file, `leiden()` | `RBConfigurationVertexPartition`, resolution 1.0, seed 42 → 11 communities over 14,807 works |
| write the assignment | same file | `data/exports/work_communities.csv` |
| describe each community | [`src/checkpoint.py:161-164`](../biophoton-fieldmap/src/checkpoint.py#L163) | `rep_works[0]` = the single highest `cited_by_count` in the community |

```bash
# the exact ten, from the shipped artefact
python -c "import pandas as pd; d=pd.read_csv('data/exports/work_communities.csv'); print(d[d.coupling_community==0].nlargest(10,'cited_by_count')[['title','cited_by_count','hop','is_seed']])"
```

All ten are `hop=2` and `is_seed=0`.

---

## 2. Four mechanisms, in order of how much damage they do

### 2.1 `cited_by_count` is anti-correlated with cluster membership

Citation count measures a work's standing in the world literature. Cluster
membership is a property of the local coupling graph. Inside community 0 the two
run in opposite directions:

| citations | works | median coupling degree | median in-universe references |
|---|---|---|---|
| 0–25 | 2,603 | **85** | 13 |
| 26–100 | 1,496 | 64 | 10 |
| 101–500 | 794 | 37 | 7 |
| 501–2,000 | 238 | 28 | 6 |
| > 2,000 | 62 | **19** | 4.5 |

The reason is structural. Hyper-cited classics enter the universe as hop-2
forward-citation neighbours; their own reference lists barely intersect the
harvest, so they arrive as near-isolated nodes. "Quantum Mechanical Continuum
Solvation Models" has **2** coupling neighbours in a 5,193-node cluster.
"Emotion Circuits in the Brain" has 2. "Hallmarks of Cancer" has 10, against a
cluster median of 66.

Ranking a cluster by citations therefore selects, systematically, its *least*
representative members. 3% of community 0's hundred most-cited works carry a
photon/luminescence term in the title; 24% of the community as a whole does.

### 2.2 The coupling graph is built by a handful of reference hubs

`build_coupling` makes every pair of works citing a common reference into an
edge. Reference popularity is heavy-tailed, so a few references dominate:

- 84 of the 13,473 shared references (**0.6%**) generate **63%** of all coupling
  pairs.
- Rayleigh 1917, _On the pressure developed in a liquid during the collapse of a
  spherical cavity_, generates 619k pairs by itself; _The Acoustic Bubble_, 415k.

A reference cited by 900 universe works says nothing about which two of them
belong together. Raw shared-reference counts also favour long reference lists
without normalising for them, so weight ≥ 2 is a much lower bar for a review
with 200 references than for a paper with 12.

### 2.3 Leiden must place every node, so the periphery gets a label it hasn't earned

654 of community 0's 5,193 works (12.6%) have coupling degree ≤ 10; 140 have
degree ≤ 2. These are not members of anything — they are nodes the algorithm had
to park somewhere. Because they carry no structural weight they never influence
the cluster, but they dominate every citation-ranked list drawn from it.

### 2.4 The hop-2 ring is three quarters of the cluster

Community 0 is 125 seeds, 1,179 hop-1 works and **3,889 hop-2 works**. The
hop-2 admission rule (`HOP2_MIN_LINKS = 3`) admits anything with three links
into the hop-1 ring, which for a hub-driven graph is a weak filter.

---

## 3. What this does *not* invalidate

Do not overcorrect. Three findings survive intact and were re-tested against a
rebuilt graph (§4.2):

- **The field-boundary answer.** Sonoluminescence seeds and UPE seeds land in
  distinct communities under both the current and the normalised partition.
  Milestone 2's analytical conclusion stands.
- **The sub-division of community 0.** [`src/subdivide.py`](../biophoton-fieldmap/src/subdivide.py)
  already filters citation magnets (`CITATION_MAGNET = 8000`) and ranks
  representatives among seed-anchored works. Its output —
  `outputs/community0_subdivision.md` — reads correctly, which is the evidence
  that the defect is in the description layer, not in Leiden.
- **The author-level tables.** They are computed from co-authorship and seed
  connectedness, not from `cited_by_count` of coupling members.

The claim to retire is narrower than it looks: *community 0 as published is a
UPE core with a large generic-science halo attached, and it was described by the
halo.*

---

## 4. The strategy

Seven steps, ordered by leverage per unit of work. Steps 4.1–4.3 are built and
measured, 4.5 is half-built, and 4.4, 4.6 and 4.7 are specified but not built.
Every method choice below is the one the science-mapping literature settled on;
sources are in §7.

### 4.1 Describe clusters by membership strength, never by citations — DONE

Four metrics are properties of the local graph rather than of the world, and
each is computable from artefacts already on disk
([`src/cluster_metrics.py`](../biophoton-fieldmap/src/cluster_metrics.py)):

| metric | definition | answers |
|---|---|---|
| `intra_strength` | summed coupling weight landing inside the own cluster | how much of this cluster does the work hold together? |
| `cohesion` | `intra_strength / strength` | does it belong here or to its neighbours? |
| `seed_coupling` | references shared with the seed set | is it in the same conversation as the seeds? |
| `topic_fit` | share of its OpenAlex topics among the cluster's top ten | is it on-subject? |
| `core_score` | 0–100 blend of the first, third and fourth as **within-cluster percentiles** | one sortable handle, comparable across clusters of different size |

Percentiles rather than raw values, so a 300-work sub-cluster and a 5,000-work
community stay on the same scale.

The effect on the same community 0, unchanged partition, ranked by seed
anchoring instead of citations:

1. Biophoton signaling in mediation of cell-to-cell communication (984 shared refs, 91 seeds)
2. Electromagnetic cellular interactions (797, 78)
3. Methods of Studying Ultraweak Photon Emission from Biological Objects (605, 77)
4. The application and trend of ultra-weak photon emission in biology and medicine (573, 72)
5. Biophotons, coherence and photocount statistics: A critical review (557, 78)

Same cluster, same algorithm, same data. The description was the whole problem.

**Browse it:** [`outputs/cluster_explorer.html`](../biophoton-fieldmap/outputs/cluster_explorer.html)
shows all 49 clusters with every work, sortable by any of these, with the three
rankings side by side.

### 4.2 Rebuild the graph the way the field does — BUILT AND MEASURED

The first draft of this section proposed an ad-hoc hub cap plus Salton
normalisation. Both were replaced with the established equivalents, which do the
same job with citations behind them.

**Fractional counting instead of raw shared-reference counts.** A reference
shared by *n* works contributes 1/(*n*−1) to each pair it creates rather than 1
(Perianes-Rodríguez, Waltman & van Eck, 2016). Rayleigh's cavitation paper, with
2,390 citers in this universe, now contributes 0.0004 to a link instead of 1 —
the hub problem disappears without an arbitrary cutoff, and the authors conclude
that "for many purposes the fractional counting approach is preferable over the
full counting one".

**Constant Potts Model instead of modularity.** `RBConfigurationVertexPartition`
is a modularity variant and inherits modularity's resolution limit: below a
scale set by total graph size, genuinely separate groups get merged — which is
exactly what a 5,193-work blob looks like. CPM is resolution-limit free (Traag,
Van Dooren & Nesterov, 2011; Traag, Waltman & van Eck, 2019) and its resolution
parameter is an interpretable internal link-density threshold.

**Bibliographic coupling stays.** This is the one existing choice the literature
endorses: Waltman, Boyack, Colavizza & van Eck (2020) find that "bibliographic
coupling relations yield more accurate clustering solutions than direct citation
relations and co-citation relations", with extended direct citation "similarly
to or slightly better". Klavans & Boyack (2017) reached the opposite conclusion
in favour of direct citation, so the point is contested — but the pipeline's
existing choice sits on the defensible side, and switching is not the priority.

Implemented in [`src/coupling.py`](../biophoton-fieldmap/src/coupling.py) and
[`src/recluster.py`](../biophoton-fieldmap/src/recluster.py).

**Choosing the resolution.** CPM's parameter is swept rather than guessed
(`python src/recluster.py --sweep`). Seed capture and topical purity trade off
monotonically:

| resolution | clusters | ≥20 works | largest | UPE home | seeds | seed capture | photon-term titles |
|---|---|---|---|---|---|---|---|
| 0.0005 | 728 | 17 | 6,874 | 4,507 | 105 | 0.54 | 18% |
| 0.001 | 573 | 33 | 5,801 | 1,507 | 90 | 0.46 | 49% |
| 0.002 | 636 | 43 | 2,533 | 1,142 | 80 | 0.41 | 51% |
| **0.004** | **799** | **82** | **1,745** | **720** | **72** | **0.37** | **67%** |
| 0.008 | 1,198 | 104 | 1,012 | 435 | 60 | 0.31 | 79% |
| 0.016 | 1,783 | 131 | 521 | 239 | 46 | 0.24 | 86% |
| 0.032 | 2,847 | 138 | 279 | 139 | 37 | 0.19 | 92% |

0.004 is the recommended setting, not a forced one: it is where the blob is gone
(largest cluster 1,745, no giant component) and purity has risen sharply, before
the steep seed-shedding sets in. The whole curve is in the table so the choice
stays reviewable.

**Result at 0.004** (`outputs/recluster_comparison.md`):

| | v1 (current) | v2 |
|---|---|---|
| counting | full, weight ≥ 2 | fractional |
| quality function | RBConfiguration | CPM |
| edges | 2,392,824 | 9,637,561 |
| clusters | 11 | 799 (82 with ≥ 20 works) |
| largest cluster | 5,193 | 1,745 |
| works unassigned | 3,548 | 2,614 |
| **UPE home** | c0: 5,193 works, 125 seeds | **v6: 720 works, 72 seeds** |
| photon/luminescence titles in it | 24% | **67%** |
| the ten citation magnets | all in c0 | **scattered across ten different clusters, none of them v6** |
| sonoluminescence boundary | distinct | **still distinct** (v3) |

The old community 0 disperses across at least eight v2 clusters — 823 works to
v5, 680 to v6, 421 to v9, 404 to v7, and so on. There was never one core; there
was a blob.

### 4.3 Report cluster stability, because Leiden is stochastic — BUILT AND MEASURED

A partition published without a reproducibility figure is a partition whose
reproducibility is unknown. `recluster.py` runs Leiden ten times with different
random seeds and reports two things: the adjusted Rand index between runs, and a
per-work consensus score (the share of a work's cluster that stays with it
across runs).

Overall the v2 partition is solid — ARI **0.814 ± 0.061**, mean node stability
**0.811**. Per cluster it is not uniform, and that is the useful part:

| cluster | works | seeds | stability |
|---|---|---|---|
| v3 — sonoluminescence | 875 | 25 | **0.94** |
| v4 | 852 | 0 | 0.94 |
| v5 | 827 | 3 | 0.93 |
| v0 | 1,745 | 9 | 0.88 |
| **v6 — UPE home** | **720** | **72** | **0.70** |
| v9 | 423 | 5 | 0.67 |
| v10 | 356 | 4 | **0.42** |

Two readings follow directly. The sonoluminescence adjacency is rock solid, so
the Milestone-2 boundary finding is safe to publish as-is. The UPE home is not:
its stability distribution is bimodal — median 0.83, tenth percentile 0.24 —
with 539 of its 720 works (75%) sitting at exactly the modal value. Three
quarters of v6 is a hard core that always clusters together; 19% of it lands
below 0.5 and floats between runs. And v10, at 0.42, is a cluster that
should carry a caveat rather than a label.

Stability is a sortable column in the explorer, so the floating members are one
click away.

### 4.4 Make the periphery an explicit class

Emit `degree`, `cohesion` and a `periphery` flag alongside the community column;
exclude flagged works from every count, exemplar and label, and report them as
their own line so the totals still reconcile. A cluster of "5,193 works" of
which 654 are degree ≤ 10 should be published as "4,539 works plus a 654-work
periphery."

### 4.5 Restrict to research contributions — FLAG BUILT, NOT YET RUN

The universe clusters 40 paratext records, 43 reference entries, 34 book
reviews, 17 editorials, 7 errata and 6 peer-review reports as if they were
research papers; v2's UPE home alone contains five peer-review records and two
paratext entries.
Publication-level classifications restrict to research contributions (Waltman &
van Eck, 2012). `recluster.py --research-types-only` applies the filter and drops
344 records.

Separately, **660 works share an exact title with another work** (291 distinct
titles) — preprint/version-of-record pairs and OpenAlex duplicates, inflating
every cluster count. Deduplication is not implemented; it should be, before any
count goes into the book chapter.

Neither was folded into the v2 run above, because both change every downstream
number and that is a decision to take once, deliberately.

### 4.6 Tighten hop-2 admission

Three links into the hop-1 ring is a weak gate when the ring is hub-driven.
Options, cheapest first: require the three links to be to *distinct* hop-1 works
not sharing a hub reference; require a minimum fractional-counting similarity to
any seed; or require topical overlap with `CORE_TOPIC_HINTS`. Rerunning the
harvest is expensive, so test the gate against the existing universe first.

### 4.7 Label clusters by distinctive terms, not by an exemplar

Replace the "Most-cited work" line in
[`src/checkpoint.py:163`](../biophoton-fieldmap/src/checkpoint.py#L163) with:

- top distinctive title terms by weighted log-odds against the whole universe
  (implemented in `build_cluster_explorer.distinctive_terms`);
- three exemplars chosen by `core_score`, not by citations;
- seed count, median degree, periphery count and stability, so a reader can see
  how solid the cluster is.

The v2 clusters label themselves cleanly this way: v6 is *emission · photon ·
ultraweak*, v3 is *sonoluminescence · single-bubble · bubble*. The old community
0 labels as *quantum · photon · emission · consciousness · brain ·
electromagnetic* — a fair description of a cluster that really did bundle UPE
with quantum biology and consciousness research, and an honest signal that it
wanted splitting.

---

## 5. Acceptance gates

Before any partition replaces the current one:

| # | gate | v1 | v2 |
|---|---|---|---|
| 1 | sonoluminescence and UPE seeds in distinct clusters | pass | **pass** |
| 2 | no work in the UPE home's top ten exemplars has `seed_coupling = 0` | **4 of 10 do** | **0 of 10 — pass** |
| 3 | ≥ 40% of the UPE home's titles carry a photon/luminescence term | 24% | **67%** |
| 4 | ARI across reruns ≥ 0.75 | not measured | **0.814** |
| 5 | every published count reconciles to 18,355 works | pass | **pass** |
| 6 | seed capture in the largest home ≥ 125/245 | 125 | **72 — fails** |

Gate 6 is the one v2 does not clear, and it is a real cost, not a rounding
error. The reading is that the 125-seed figure was itself inflated: v1 held
seeds together partly through hub references that fractional counting correctly
discounts. Whether 72 tightly-held seeds beat 125 loosely-held ones is an
editorial judgement — see below.

---

## 6. Open decisions

- **Resolution.** 0.004 is recommended; the full trade-off curve is in §4.2 and
  the sweep costs ~5 minutes. Martin's call.
- **Whether v2 replaces v1 or sits beside it.** The explorer now carries both
  partitions, so the honest option is to publish v1 as shipped, v2 as the
  corrected map, and the comparison as a methods note.
- **Document-type filter and deduplication** (§4.5). Both are cheap and both
  invalidate every existing count. Do them together or not at all.
- **Whether the "UPE core" should be a single cluster at all.** `subdivide.py`
  already showed a *family* of strands — the eight seed-bearing sub-clusters 1,
  9, 4, 2, 0, 15, 19 and 18. v2 says the same thing from a different direction,
  and v6's bimodal stability says it a third time. Publishing the family, with
  per-strand counts and stability, is more defensible than publishing one
  cluster and apologising for its halo.

---

## 7. References

Klavans, R., & Boyack, K. W. (2017). Which type of citation analysis generates
the most accurate taxonomy of scientific and technical knowledge? *Journal of the
Association for Information Science and Technology*, 68(4), 984–998.
https://doi.org/10.1002/asi.23734

Perianes-Rodríguez, A., Waltman, L., & van Eck, N. J. (2016). Constructing
bibliometric networks: A comparison between full and fractional counting.
*Journal of Informetrics*, 10(4), 1178–1195.
https://doi.org/10.1016/j.joi.2016.10.006

Šubelj, L., van Eck, N. J., & Waltman, L. (2016). Clustering scientific
publications based on citation relations: A systematic comparison of different
methods. *PLOS ONE*, 11(4), e0154404.
https://doi.org/10.1371/journal.pone.0154404

Traag, V. A., Van Dooren, P., & Nesterov, Y. (2011). Narrow scope for
resolution-limit-free community detection. *Physical Review E*, 84(1), 016114.
https://doi.org/10.1103/PhysRevE.84.016114

Traag, V. A., Waltman, L., & van Eck, N. J. (2019). From Louvain to Leiden:
guaranteeing well-connected communities. *Scientific Reports*, 9(1), 5233.
https://doi.org/10.1038/s41598-019-41695-z

Waltman, L., Boyack, K. W., Colavizza, G., & van Eck, N. J. (2020). A principled
methodology for comparing relatedness measures for clustering publications.
*Quantitative Science Studies*, 1(2), 691–713.
https://doi.org/10.1162/qss_a_00035

Waltman, L., & van Eck, N. J. (2012). A new methodology for constructing a
publication-level classification system of science. *Journal of the American
Society for Information Science and Technology*, 63(12), 2378–2392.
https://doi.org/10.1002/asi.22748

Waltman, L., van Eck, N. J., & Noyons, E. C. M. (2010). A unified approach to
mapping and clustering of bibliometric networks. *Journal of Informetrics*, 4(4),
629–635. https://doi.org/10.1016/j.joi.2010.07.002
