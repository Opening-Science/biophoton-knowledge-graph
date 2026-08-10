"""Bibliographic-coupling graph construction, following current practice.

`networks.build_coupling` links two works by the *raw* count of shared
references and keeps every pair at weight >= 2 ("full counting"). That makes a
handful of enormous references dominate the graph: 84 of the 13,473 shared
references generate 63% of all coupling pairs, and Rayleigh's 1917 cavitation
paper alone generates 619k of them.

The literature's answer is fractional counting (Perianes-Rodríguez, Waltman &
van Eck, 2016, *J. Informetrics* 10(4), 1178-1195). A reference shared by n
works spreads a fixed budget over the pairs it creates, so its contribution to
each pair is 1/(n-1) rather than 1. A reference cited by 2,390 universe works
then contributes 0.0004 to a link instead of 1, and no arbitrary hub cutoff is
needed. The authors conclude that "for many purposes the fractional counting
approach is preferable over the full counting one".

Both counting schemes reduce to one sparse product:

    C = A · diag(v) · Aᵀ            A[i,r] = 1 iff work i cites reference r
                                    v_r = 1                    (full)
                                    v_r = 1/(n_r - 1)          (fractional)

Optionally the result is normalised by association strength (Waltman, van Eck &
Noyons, 2010, *J. Informetrics* 4(4), 629-635), the similarity measure VOSviewer
and the CWTS mapping work are built on:

    s_ij = w_ij / (w_i · w_j / 2m)

Keeping bibliographic coupling as the relatedness measure is itself the
evidence-backed choice: Waltman, Boyack, Colavizza & van Eck (2020, *Quantitative
Science Studies* 1(2), 691-713) find that "bibliographic coupling relations
yield more accurate clustering solutions than direct citation relations and
co-citation relations", with extended direct citation performing "similarly to
or slightly better".
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.sparse as sp

__all__ = ["build_matrix", "coupling_matrix", "to_edges", "reference_stats"]


def build_matrix(edges: pd.DataFrame) -> tuple[sp.csr_matrix, list[str], np.ndarray]:
    """Works x references incidence matrix. Returns (A, work_ids, n_citers)."""
    src = edges["src_work_id"].astype("category")
    dst = edges["dst_work_id"].astype("category")
    A = sp.csr_matrix(
        (np.ones(len(edges), dtype=np.float64),
         (src.cat.codes.to_numpy(), dst.cat.codes.to_numpy())),
        shape=(len(src.cat.categories), len(dst.cat.categories)))
    A.data[:] = 1.0                      # collapse any duplicate edge rows
    A.sum_duplicates()
    A.data[:] = 1.0
    n_citers = np.asarray(A.sum(axis=0)).ravel()
    return A, list(src.cat.categories), n_citers


def coupling_matrix(A: sp.csr_matrix, n_citers: np.ndarray, *,
                    counting: str = "fractional",
                    assoc_strength: bool = False,
                    min_weight: float = 0.0) -> sp.coo_matrix:
    """Upper-triangular coupling weights under the requested counting scheme."""
    if counting == "fractional":
        v = np.where(n_citers >= 2, 1.0 / np.maximum(n_citers - 1.0, 1.0), 0.0)
    elif counting == "full":
        v = np.where(n_citers >= 2, 1.0, 0.0)
    else:
        raise ValueError(f"unknown counting scheme {counting!r}")

    C = (A.multiply(1.0)) @ sp.diags(v) @ A.T
    C = sp.triu(C.tocsr(), k=1).tocoo()

    w = C.data
    if assoc_strength:
        strength = np.asarray(sp.triu(C, k=0).sum(axis=1)).ravel() + \
                   np.asarray(sp.triu(C, k=0).sum(axis=0)).ravel()
        total = w.sum() * 2.0
        expected = strength[C.row] * strength[C.col] / total
        w = np.divide(w, expected, out=np.zeros_like(w),
                      where=expected > 0)

    keep = w > min_weight
    return sp.coo_matrix((w[keep], (C.row[keep], C.col[keep])), shape=C.shape)


def to_edges(C: sp.coo_matrix, work_ids: list[str]):
    """(edge index pairs, weights) for igraph, plus the node ids that survive."""
    used = np.unique(np.concatenate([C.row, C.col]))
    remap = np.full(C.shape[0], -1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    pairs = np.column_stack([remap[C.row], remap[C.col]])
    return pairs, C.data, [work_ids[i] for i in used]


def reference_stats(n_citers: np.ndarray) -> dict:
    """How concentrated is the coupling mass in a few hub references?"""
    n = n_citers[n_citers >= 2]
    pairs = n * (n - 1) / 2
    order = np.argsort(-pairs)
    cum = np.cumsum(pairs[order]) / pairs.sum()
    return {
        "shared_references": int(len(n)),
        "total_pairs_full_counting": int(pairs.sum()),
        "refs_for_50pct_of_pairs": int(np.searchsorted(cum, 0.50) + 1),
        "refs_for_63pct_of_pairs": int(np.searchsorted(cum, 0.63) + 1),
        "largest_reference_citers": int(n.max()),
    }
