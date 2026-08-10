# Re-clustering comparison — fractional counting + CPM

_fractional counting · CPM · resolution 0.004 · 10 Leiden runs · base seed 42_

Method choices and their sources are documented in [`src/coupling.py`](../src/coupling.py) and [`src/recluster.py`](../src/recluster.py); the reasoning is in [`docs/CLUSTERING_STRATEGY.md`](../../docs/CLUSTERING_STRATEGY.md).

## Graph

| | current (`networks.py`) | v2 |
|---|---|---|
| counting | full, weight ≥ 2 | fractional |
| quality function | RBConfiguration | CPM |
| nodes | 14,807 | 15,741 |
| edges | 2,392,824 | 9,637,561 |
| clusters | 11 | 799 |
| works unassigned | 3,548 | 2,614 |
| largest cluster | 5,193 | 1,745 |
| ARI across reruns | not measured | **0.814 ± 0.061** |
| mean node stability | not measured | **0.811** |

## The UPE home

| | current community 0 | v2 community 6 |
|---|---|---|
| works | 5,193 | 720 |
| seeds | 125 | 72 |
| median year | 2012 | 2015 |
| photon/luminescence titles | 24% | **67%** |
| mean node stability | — | 0.702 |

## Field boundary (the Milestone-2 finding)

Sonoluminescence seeds concentrate in v2 community **3**, non-sonoluminescence seeds in **6** — still distinct.

## Where the ten citation magnets went

| work | cites | current | v2 |
|---|---|---|---|
| Hallmarks of Cancer: The Next Generation | 66,806 | 0 | 102 |
| Quantum Mechanical Continuum Solvation Models | 16,599 | 0 | 101 |
| Calcium's Role in Mechanotransduction during Muscle Developm | 14,545 | 0 | 10 |
| On the Einstein Podolsky Rosen paradox | 12,270 | 0 | 78 |
| Quantum entanglement | 10,068 | 0 | 5 |
| Emotion Circuits in the Brain | 8,410 | 0 | 174 |
| Electron transfers in chemistry and biology | 8,027 | 0 | 144 |
| The free-energy principle: a unified brain theory? | 7,950 | 0 | 121 |
| Event-related EEG/MEG synchronization and desynchronization: | 7,134 | 0 | 26 |
| Signaling Recognition Events with Fluorescent Sensors and Sw | 6,945 | 0 | 93 |

## Where the current community 0 dispersed to

| v2 community | works from old c0 |
|---|---|
| 5 | 823 |
| 6 | 680 |
| 9 | 421 |
| 7 | 404 |
| 10 | 344 |
| 12 | 230 |
| 13 | 223 |
| 19 | 161 |
