
## Stage B — expansion (batched)

=== Stage B: 2-hop expansion (batched, key-aware) ===
Seeds: 245
  [hop1] backward+related: 245 sources -> 9566 ref-links, 8183 distinct candidates so far
    [hop1] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
  [hop1] forward (batched): 7669 distinct citing works (1 batches hit the per-batch cap)
  [hop1] prune >= 2 links: 15029 candidates -> 2393 kept, 12636 dropped
After hop-1: universe = 2638 works (2393 new)
  [hop2] backward+related: 2393 sources -> 130790 ref-links, 83373 distinct candidates so far
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
    [hop2] forward-cite CAP hit on a batch: kept top 3000 by cited_by_count
  [hop2] forward (batched): 75680 distinct citing works (26 batches hit the per-batch cap)
  [hop2] prune >= 3 links: 148092 candidates -> 15923 kept, 132169 dropped
After hop-2: universe = 18561 works (15923 new)
Fetching/caching 18561 universe works...
Wrote universe_ids.json (18561 works). OpenAlex requests this run: 620

## Stage C — DB build

- works: 18355
- authors: 39312
- institutions: 10942
- work_authors: 65860
- topics: 52039
- citation_edges: 264653
- works by hop: {0: 245, 1: 2354, 2: 15756}
- OpenAlex requests: 787

## Stage D — networks

```json
{
  "coauthorship": {
    "authors": 39312,
    "edges": 154448,
    "communities": 5918
  },
  "coupling": {
    "works": 14807,
    "edges": 2392824,
    "communities": 11
  },
  "cocitation": {
    "works": 13191,
    "edges": 831766,
    "communities": 10
  },
  "topics": {
    "topics": 2206,
    "edges": 13098,
    "communities": 81
  },
  "boundary": {
    "sonoluminescence_seed_works": 52,
    "sono_community_distribution": {
      "4": 34,
      "1": 10,
      "2": 1,
      "6": 2
    },
    "upe_core_community_distribution": {
      "0": 36
    },
    "sono_top_community": 4,
    "upe_top_community": 0,
    "distinct": true
  }
}
```

## Stage E — openness

```json
{
  "works_scored": 18355,
  "oa_share_works": 0.377,
  "works_with_preprint": 7301,
  "works_with_open_signal": 29,
  "authors_scored": 39308,
  "mean_author_openness": 0.396
}
```

## Stage G — ranking

- ranked researchers: 30380

## Stage F — contacts

- routed 200; ORCID 167; emails 17; PDF attempts 162

## Stage G — ranking

- ranked researchers: 30380

## Stage H — synthesis

- field_state.md + knowledge_map.html written

## Stage H — synthesis

- field_state.md + knowledge_map.html written

## Stage H — synthesis

- field_state.md + knowledge_map.html written

## Stage F — contacts

- routed 500; ORCID 394; emails 37; PDF attempts 248

## Stage G — ranking

- ranked researchers: 30380

## Stage H — synthesis

- field_state.md + knowledge_map.html written

## Stage G — ranking

- ranked researchers: 30380

## Stage H — synthesis

- field_state.md + knowledge_map.html written

## Stage H — synthesis

- field_state.md + knowledge_map.html written

## Stage H — synthesis

- field_state.md + knowledge_map.html written
