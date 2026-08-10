# Biophoton / UPE literature corpus

Everything the field map can reach as a file, in one folder. Built by `biophoton-fieldmap/src/harvest_oa_pdfs.py` (open-access harvest) and `consolidate_literature.py` (hand-collected material + this index).

## Open-access harvest

- **4,343 of 6,842** open-access works retrieved (63%), 11.3 GB, in `papers/`.
- Filenames are `<year>_<FirstAuthor>_<OpenAlexID>.pdf`, so the folder sorts chronologically and every file joins back to `manifest.csv` and the field-map database on its work id.
- The universe itself holds 18,355 works; the 11,513 that are not open access are listed in the map but cannot be fetched.

| Decade | PDFs |
| --- | ---: |
| 1890s | 1 |
| 1910s | 1 |
| 1920s | 9 |
| 1930s | 10 |
| 1940s | 3 |
| 1950s | 10 |
| 1960s | 20 |
| 1970s | 36 |
| 1980s | 54 |
| 1990s | 164 |
| 2000s | 573 |
| 2010s | 1,823 |
| 2020s | 1,638 |

### Not retrieved (2,499)

Flagged open access by OpenAlex, but no file could be pulled from an identified, rate-limited robot. Most are publishers that answer `403` to anything that is not a browser. No impersonation was attempted, so these stay as links: each row in `manifest.csv` carries the DOI and the reason, which is what an institutional login or an interlibrary request needs.

| Reason | Works |
| --- | ---: |
| `landing-page` | 908 |
| `http-403` | 824 |
| `host-cooling-off` | 230 |
| `http-404` | 135 |
| `http-500` | 125 |
| `http-202` | 110 |

## Books

Book-length works, added by hand.

- **Ultra-Weak Photon Emission from Biological Systems: Endogenous Biophotonics and Intrinsic Bioluminescence**  
  Volodyaev, van Wijk, Cifra & Vladimirov (eds.) · 2023  
  `books/2023_Volodyaev-etal_Ultra-Weak-Photon-Emission-from-Biological-Systems.pdf` · doi:10.1007/978-3-031-39078-4  
  _in corpus (W4389669809), also harvested_ — Springer reference volume, 511 pp. The field's standard edited survey.

## Curated papers

Hand-collected PDFs. The cross-reference says how each relates to the mapped field -- including the two metrology papers, which sit outside it deliberately.

- **Biophotons, coherence and photocount statistics: a critical review**  
  Cifra, Brouder, Nerudová & Kučera · 2015  
  `curated/2015_Cifra_Biophotons-coherence-and-photocount-statistics-arXiv-preprint.pdf` · doi:10.1016/j.jlumin.2015.03.020  
  _in corpus (W2141663490), also harvested_ — arXiv:1502.07316v1 preprint of the J. Luminescence review; the corpus copy is the green OA version.
- **Comparison at the sub-100 fW optical power level of calibrating a single-photon detector using a high-sensitive, low-noise silicon photodiode and the double attenuator technique**  
  Porrovecchio et al. · 2016  
  `curated/2016_Porrovecchio_Sub-100-fW-single-photon-detector-calibration-comparison.pdf` · doi:10.1088/0026-1394/53/4/1115  
  _not in the mapped universe_ — Detector-calibration metrology; outside the mapped biophoton universe.
- **A study to develop a robust method for measuring the detection efficiency of free-running InGaAs/InP single-photon detectors**  
  López et al. · 2020  
  `curated/2020_Lopez_Detection-efficiency-of-free-running-InGaAs-InP-single-photon-detectors.pdf` · doi:10.1140/epjqt/s40507-020-00089-1  
  _not in the mapped universe_ — Detector-efficiency metrology; outside the mapped biophoton universe.
- **Revisiting Claims of Extracranial Biophoton Detection from the Human Brain**  
  Salari et al. · 2026  
  `curated/2026_Salari_Revisiting-Claims-of-Extracranial-Biophoton-Detection-from-the-Human-Brain.pdf` · doi:10.1021/acs.jpclett.6c01258  
  _in corpus (W7168813583) but CLOSED access -- this copy fills the gap_ — J. Phys. Chem. Lett. 2026.
- **All living things emit a faint glow. Could this light be useful?**  
  Nature (news feature) · 2025  
  `curated/2025_Nature-news_All-living-things-emit-a-faint-glow.pdf`  
  _not in the mapped universe_ — Journalism, not a research article; useful for framing.

## Files

| Path | What |
| --- | --- |
| `papers/` | harvested open-access corpus |
| `books/` | book-length works |
| `curated/` | hand-collected papers |
| `project_docs/` | OSF-internal working documents (local only, untracked, unindexed) |
| `manifest.csv` | every OA work: id, doi, outcome, sha256, source |
| `curated.csv` | curated items + corpus cross-reference |
| `harvest_log.jsonl` | per-attempt audit trail (resumability) |

Rerunning the harvester skips what is already on disk; `--retry-failed` re-attempts the misses.

PDFs are not committed to git — the folder is gitignored apart from this index and the two CSVs, which are enough to rebuild it.