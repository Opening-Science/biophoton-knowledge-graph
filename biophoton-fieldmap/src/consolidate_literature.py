"""Fold hand-collected material into the harvested corpus and index the lot.

`harvest_oa_pdfs.py` fills literature/papers/ from OpenAlex. This stage adds
the things OpenAlex cannot give us -- a 511-page Springer volume, papers behind
paywalls that were obtained by hand, metrology literature from outside the
biophoton universe entirely -- and writes the one index that describes
everything in the folder.

Curated items are cross-referenced against the field map by DOI, so the index
says which of them the corpus already covers, which are closed-access gaps the
hand copy fills, and which sit outside the mapped field. That distinction is
the point: the metrology papers are outside it on purpose.

Sources are explicit. Nothing is swept in from a folder that also holds
personal or financial documents.

Outputs under <repo root>/literature/:
  books/         book-length works
  curated/       hand-collected papers
  project_docs/  OSF's own drafts about this literature
  curated.csv    curated items + corpus cross-reference
  INDEX.md       readable index of the whole folder
"""
from __future__ import annotations

import csv
import re
import shutil
from pathlib import Path

import pandas as pd

import config as C

LIT = C.ROOT.parent / "literature"
PAPERS = LIT / "papers"
BOOKS = LIT / "books"
CURATED = LIT / "curated"
PROJECT_DOCS = LIT / "project_docs"

# Machine-local source roots and any OSF-internal documents live in a
# gitignored JSON beside the repo (see _local_sources) so no personal paths
# or unpublished-project filenames enter the public repository.
LOCAL_SOURCES = C.ROOT.parent / ".literature_sources.json"


def _local_sources() -> dict:
    """{"roots": {name: path}, "project_docs": [{src, name, title, note}]}"""
    if LOCAL_SOURCES.exists():
        import json as _json
        return _json.loads(LOCAL_SOURCES.read_text())
    print(f"  note: {LOCAL_SOURCES.name} not found -- curated sources that "
          f"need it are skipped")
    return {"roots": {}, "project_docs": []}


_LOCAL = _local_sources()
PROTON = Path(_LOCAL.get("roots", {}).get("proton", "/nonexistent"))
DOWNLOADS = Path(_LOCAL.get("roots", {}).get("downloads", "/nonexistent"))

# Explicit, reviewed sources. Metadata is hand-checked against each PDF's own
# title page rather than guessed, because these are the items the index leans
# on to explain what the corpus does not cover.
BOOK_SOURCES = [
    dict(src=DOWNLOADS / "Biophotonics_2023.pdf",
         name="2023_Volodyaev-etal_Ultra-Weak-Photon-Emission-from-"
              "Biological-Systems.pdf",
         title="Ultra-Weak Photon Emission from Biological Systems: "
               "Endogenous Biophotonics and Intrinsic Bioluminescence",
         authors="Volodyaev, van Wijk, Cifra & Vladimirov (eds.)",
         year=2023, doi="10.1007/978-3-031-39078-4",
         note="Springer reference volume, 511 pp. The field's standard "
              "edited survey."),
]

CURATED_SOURCES = [
    dict(src=PROTON / "1502.07316v1.pdf",
         name="2015_Cifra_Biophotons-coherence-and-photocount-statistics-"
              "arXiv-preprint.pdf",
         title="Biophotons, coherence and photocount statistics: "
               "a critical review",
         authors="Cifra, Brouder, Nerudová & Kučera",
         year=2015, doi="10.1016/j.jlumin.2015.03.020",
         note="arXiv:1502.07316v1 preprint of the J. Luminescence review; "
              "the corpus copy is the green OA version."),
    dict(src=PROTON / "Porrovecchio_2016_Metrologia_53_1115.pdf",
         name="2016_Porrovecchio_Sub-100-fW-single-photon-detector-"
              "calibration-comparison.pdf",
         title="Comparison at the sub-100 fW optical power level of "
               "calibrating a single-photon detector using a "
               "high-sensitive, low-noise silicon photodiode and the "
               "double attenuator technique",
         authors="Porrovecchio et al.",
         year=2016, doi="10.1088/0026-1394/53/4/1115",
         note="Detector-calibration metrology; outside the mapped "
              "biophoton universe."),
    dict(src=PROTON / "s40507-020-00089-1.pdf",
         name="2020_Lopez_Detection-efficiency-of-free-running-InGaAs-InP-"
              "single-photon-detectors.pdf",
         title="A study to develop a robust method for measuring the "
               "detection efficiency of free-running InGaAs/InP "
               "single-photon detectors",
         authors="López et al.",
         year=2020, doi="10.1140/epjqt/s40507-020-00089-1",
         note="Detector-efficiency metrology; outside the mapped "
              "biophoton universe."),
    dict(src=PROTON / "Salari_2026.pdf",
         name="2026_Salari_Revisiting-Claims-of-Extracranial-Biophoton-"
              "Detection-from-the-Human-Brain.pdf",
         title="Revisiting Claims of Extracranial Biophoton Detection "
               "from the Human Brain",
         authors="Salari et al.",
         year=2026, doi="10.1021/acs.jpclett.6c01258",
         note="J. Phys. Chem. Lett. 2026."),
    dict(src=PROTON / "All living things emit a faint glow. Could this "
                      "light be useful_ _ Nature.pdf",
         name="2025_Nature-news_All-living-things-emit-a-faint-glow.pdf",
         title="All living things emit a faint glow. Could this light "
               "be useful?",
         authors="Nature (news feature)",
         year=2025, doi="",
         note="Journalism, not a research article; useful for framing."),
]

# OSF-internal working documents (drafts, templates). Defined in the local
# JSON, copied to project_docs/ for convenience, and kept OUT of the tracked
# index and curated.csv: they are project material, not literature.
PROJECT_DOC_SOURCES = [
    dict(src=Path(d["src"]), name=d["name"], title=d.get("title", d["name"]),
         note=d.get("note", ""))
    for d in _LOCAL.get("project_docs", [])
]


def norm_doi(d: str) -> str:
    return (d or "").replace("https://doi.org/", "").strip().lower()


def copy_in(src: Path, dest_dir: Path, name: str) -> tuple[str, int]:
    """Copy a source PDF in under a descriptive name. Returns (name, bytes)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name
    if not src.exists():
        return "", 0
    if not dest.exists() or dest.stat().st_size != src.stat().st_size:
        shutil.copy2(src, dest)
    return dest.name, dest.stat().st_size


def cross_reference() -> tuple[pd.DataFrame, pd.DataFrame]:
    works = pd.read_parquet(C.EXPORTS / "works.parquet")
    works["d"] = works["doi"].fillna("").map(norm_doi)
    manifest = LIT / "manifest.csv"
    harvested = (pd.read_csv(manifest) if manifest.exists()
                 else pd.DataFrame(columns=["work_id", "status", "doi",
                                            "bytes", "year", "reason"]))
    return works, harvested


def main() -> None:
    LIT.mkdir(parents=True, exist_ok=True)
    works, harvested = cross_reference()
    got = set(harvested[harvested["status"].isin(["ok", "have"])]["work_id"]) \
        if len(harvested) else set()

    rows = []
    for group, sources, dest in (
            ("book", BOOK_SOURCES, BOOKS),
            ("paper", CURATED_SOURCES, CURATED),
            ("project_doc", PROJECT_DOC_SOURCES, PROJECT_DOCS)):
        for s in sources:
            name, size = copy_in(s["src"], dest, s["name"])
            if not name:
                print(f"  MISSING source: {s['src']}")
                continue
            doi = norm_doi(s.get("doi", ""))
            hit = works[works["d"] == doi] if doi else works.iloc[0:0]
            if group == "project_doc":
                # our own drafts; "not in the mapped universe" would be noise
                rel = "OSF working document"
            elif len(hit):
                w = hit.iloc[0]
                if w["work_id"] in got:
                    rel = f"in corpus ({w['work_id']}), also harvested"
                elif w["is_oa"] == 0:
                    rel = (f"in corpus ({w['work_id']}) but CLOSED access -- "
                           f"this copy fills the gap")
                else:
                    rel = f"in corpus ({w['work_id']}), not harvested"
            else:
                rel = "not in the mapped universe"
            if group == "project_doc":
                continue    # copied for local convenience; never indexed
            rows.append({
                "group": group,
                "file": f"{dest.name}/{name}",
                "title": s["title"],
                "authors": s.get("authors", ""),
                "year": s.get("year", ""),
                "doi": doi,
                "bytes": size,
                "corpus_relation": rel,
                "note": s.get("note", ""),
            })

    with open(LIT / "curated.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)

    write_index(rows, harvested, works)
    print(f"consolidated {len(rows)} curated items -> {LIT}")


def write_index(rows: list[dict], harvested: pd.DataFrame,
                works: pd.DataFrame) -> None:
    L: list[str] = []
    A = L.append
    A("# Biophoton / UPE literature corpus\n")
    A("Everything the field map can reach as a file, in one folder. Built by "
      "`biophoton-fieldmap/src/harvest_oa_pdfs.py` (open-access harvest) and "
      "`consolidate_literature.py` (hand-collected material + this index).\n")

    if len(harvested):
        ok = harvested[harvested["status"].isin(["ok", "have"])]
        gb = ok["bytes"].sum() / 1e9
        A("## Open-access harvest\n")
        A(f"- **{len(ok):,} of {len(harvested):,}** open-access works "
          f"retrieved ({len(ok) / max(len(harvested), 1):.0%}), "
          f"{gb:.1f} GB, in `papers/`.")
        A(f"- Filenames are `<year>_<FirstAuthor>_<OpenAlexID>.pdf`, so the "
          f"folder sorts chronologically and every file joins back to "
          f"`manifest.csv` and the field-map database on its work id.")
        A(f"- The universe itself holds {len(works):,} works; the "
          f"{len(works) - len(harvested):,} that are not open access are "
          f"listed in the map but cannot be fetched.\n")

        by_dec = ok.copy()
        by_dec["decade"] = (pd.to_numeric(by_dec["year"], errors="coerce")
                            // 10 * 10)
        counts = by_dec["decade"].value_counts().sort_index()
        A("| Decade | PDFs |")
        A("| --- | ---: |")
        for dec, n in counts.items():
            if pd.notna(dec) and dec > 0:
                A(f"| {int(dec)}s | {n:,} |")
        A("")

        miss = harvested[harvested["status"] == "failed"]
        if len(miss):
            A(f"### Not retrieved ({len(miss):,})\n")
            A("Flagged open access by OpenAlex, but no file could be pulled "
              "from an identified, rate-limited robot. Most are publishers "
              "that answer `403` to anything that is not a browser. No "
              "impersonation was attempted, so these stay as links: each row "
              "in `manifest.csv` carries the DOI and the reason, which is "
              "what an institutional login or an interlibrary request needs.\n")
            reasons = miss["reason"].fillna("").str.split(";").str[-1] \
                .str.split(":").str[-1].value_counts().head(6)
            A("| Reason | Works |")
            A("| --- | ---: |")
            for r, n in reasons.items():
                A(f"| `{r}` | {n:,} |")
            A("")

    for group, heading, blurb in (
            ("book", "Books",
             "Book-length works, added by hand."),
            ("paper", "Curated papers",
             "Hand-collected PDFs. The cross-reference says how each relates "
             "to the mapped field -- including the two metrology papers, "
             "which sit outside it deliberately.")):
        items = [r for r in rows if r["group"] == group]
        if not items:
            continue
        A(f"## {heading}\n")
        A(f"{blurb}\n")
        for r in items:
            A(f"- **{r['title']}**  ")
            meta = " · ".join(x for x in (r["authors"], str(r["year"] or ""))
                              if x)
            if meta:
                A(f"  {meta}  ")
            A(f"  `{r['file']}`"
              + (f" · doi:{r['doi']}" if r["doi"] else "") + "  ")
            A(f"  _{r['corpus_relation']}_"
              + (f" — {r['note']}" if r["note"] else ""))
        A("")

    A("## Files\n")
    A("| Path | What |")
    A("| --- | --- |")
    A("| `papers/` | harvested open-access corpus |")
    A("| `books/` | book-length works |")
    A("| `curated/` | hand-collected papers |")
    A("| `project_docs/` | OSF-internal working documents (local only, "
      "untracked, unindexed) |")
    A("| `manifest.csv` | every OA work: id, doi, outcome, sha256, source |")
    A("| `curated.csv` | curated items + corpus cross-reference |")
    A("| `harvest_log.jsonl` | per-attempt audit trail (resumability) |")
    A("")
    A("Rerunning the harvester skips what is already on disk; "
      "`--retry-failed` re-attempts the misses.\n")
    A("PDFs are not committed to git — the folder is gitignored apart from "
      "this index and the two CSVs, which are enough to rebuild it.")

    (LIT / "INDEX.md").write_text("\n".join(L))


if __name__ == "__main__":
    main()
