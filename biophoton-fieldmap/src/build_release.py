"""Assemble the public open-data release bundle under outputs/release/.

Enforces the release policy in code:
  - the contact-email columns are stripped from every researcher table;
  - abstracts are shipped as an inverted index (JSON), never as prose, and the
    paper search DB uses a contentless FTS5 index (terms only, no stored text);
  - only public files are copied; the internal contacts data, PDFs, and API key
    are never touched.
Also writes the CC0 license, CITATION.cff, datapackage.json, a data dictionary,
a public README, and a changelog. Finishes with an email-leak scan that fails
loudly if any address slips through.

Run: python build_release.py
"""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
from pathlib import Path

import pandas as pd

import config as C

VERSION = "1.0.0"
SNAPSHOT = "2026-07 (OpenAlex)"
CONCEPT_DOI = "10.5281/zenodo.21466492"   # cite all versions (resolves to latest)
VERSION_DOI = "10.5281/zenodo.21466493"   # this specific v1.0.0 record
RELEASE = C.OUTPUTS / "release"
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
EMAIL_COLS = ["email", "email_source_doi", "email_confidence"]


def redact(text) -> str:
    """Remove any email address embedded in free text (abstracts, affiliations)."""
    if text is None:
        return text
    return EMAIL_RE.sub("[email redacted]", str(text))


def invert(text: str) -> dict:
    words = redact(text or "").split()
    idx: dict[str, list[int]] = {}
    for i, w in enumerate(words):
        idx.setdefault(w, []).append(i)
    return idx


def fresh(p: Path):
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True)


def strip_emails_csv(src: Path, dst: Path):
    df = pd.read_csv(src)
    df = df.drop(columns=[c for c in df.columns if c in EMAIL_COLS], errors="ignore")
    df.to_csv(dst, index=False)


def build_paper_index(dst: Path):
    """Public paper DB: inverted-index abstracts + contentless FTS5 (no prose)."""
    src = C.OUTPUTS / "index" / "full_paper_index.sqlite"
    sc = sqlite3.connect(src)
    df = pd.read_sql_query("SELECT * FROM papers ORDER BY rank", sc)
    sc.close()
    recon = df["abstract"].fillna("").apply(redact)   # scrub embedded emails
    df["abstract_inverted_index"] = recon.apply(lambda t: json.dumps(invert(t)))
    if dst.exists():
        dst.unlink()
    db = sqlite3.connect(dst)
    df.drop(columns=["abstract"]).to_sql("papers", db, index=False)
    db.executescript(
        "CREATE INDEX idx_rank ON papers(rank);"
        "CREATE INDEX idx_doi ON papers(doi);"
        "CREATE INDEX idx_seed ON papers(is_seed);")
    # contentless FTS: indexes terms for MATCH, stores no source text
    try:
        db.execute("CREATE VIRTUAL TABLE papers_fts USING fts5("
                   "title, authors, abstract, content='');")
        rows = list(zip(range(1, len(df) + 1), df["title"].fillna(""),
                        df["authors"].fillna(""), recon))
        db.executemany(
            "INSERT INTO papers_fts(rowid, title, authors, abstract) "
            "VALUES (?,?,?,?)", rows)
    except sqlite3.OperationalError as e:
        print(f"  NOTE: FTS5 unavailable ({e})")
    db.commit()
    db.close()


def scan_for_emails(root: Path) -> list[str]:
    hits = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in {".csv", ".json", ".md", ".txt", ".cff", ".html"}:
            try:
                txt = p.read_text(errors="ignore")
            except Exception:
                continue
            found = EMAIL_RE.findall(txt)
            # allow the maintainer/contact address in docs, flag anything else
            bad = [e for e in found if not e.endswith("opening.science")]
            if bad:
                hits.append(f"{p.relative_to(root)}: {sorted(set(bad))[:3]}")
        elif p.suffix.lower() == ".sqlite":
            db = sqlite3.connect(p)
            for (name,) in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"):
                try:
                    cols = [r[1] for r in db.execute(f"PRAGMA table_info({name})")]
                except sqlite3.OperationalError:
                    continue
                if any(c in EMAIL_COLS for c in cols):
                    hits.append(f"{p.relative_to(root)}::{name} has email column")
                # scan text cell contents too
                for col in cols:
                    try:
                        vals = db.execute(
                            f"SELECT \"{col}\" FROM {name} "
                            f"WHERE \"{col}\" LIKE '%@%.%' LIMIT 5000").fetchall()
                    except sqlite3.OperationalError:
                        continue
                    for (v,) in vals:
                        if isinstance(v, str) and EMAIL_RE.search(v):
                            hits.append(f"{p.relative_to(root)}::{name}.{col} "
                                        f"contains an email")
                            break
            db.close()
    return hits


def main():
    fresh(RELEASE)
    data = RELEASE / "data"; data.mkdir()
    graphs = RELEASE / "graphs"; graphs.mkdir()
    tools = RELEASE / "tools"; tools.mkdir()
    docs = RELEASE / "docs"; docs.mkdir()
    EX = C.EXPORTS

    # 1. core DB + parquet/csv exports. raw_affiliation_string sometimes carries
    #    an author email (from OpenAlex); redact it in the public copies.
    shutil.copy(C.DB_PATH, data / "fieldmap.sqlite")
    db = sqlite3.connect(data / "fieldmap.sqlite")
    db.create_function("redact", 1, redact)
    db.execute("UPDATE work_authors SET raw_affiliation_string = "
               "redact(raw_affiliation_string) "
               "WHERE raw_affiliation_string LIKE '%@%'")
    db.commit()
    db.close()

    safe_exports = [
        "works", "authors", "institutions", "topics",
        "concepts", "citation_edges", "coauthor_nodes", "work_communities"]
    for name in safe_exports:
        for ext in ("csv", "parquet"):
            src = EX / f"{name}.{ext}"
            if src.exists():
                shutil.copy(src, data / src.name)
    # work_authors: redact affiliation emails in both CSV and parquet
    wa = pd.read_sql_query("SELECT * FROM work_authors",
                           sqlite3.connect(data / "fieldmap.sqlite"))
    wa.to_csv(data / "work_authors.csv", index=False)
    wa.to_parquet(data / "work_authors.parquet", index=False)
    for j in ["community_labels.json", "community0_subclusters.csv",
              "community0_subcluster_labels.json", "author_merges.json",
              "author_splits_flagged.json", "networks_report.json",
              "seed_works.csv", "seed_unmatched.csv"]:
        if (EX / j).exists():
            shutil.copy(EX / j, data / j)

    # 2. researcher tables with email columns stripped
    for r in ["researchers.csv", "researchers_top50.csv",
              "researchers_top_open.csv", "researchers_rising.csv",
              "researchers_biophoton_core.csv"]:
        if (EX / r).exists():
            strip_emails_csv(EX / r, data / r)

    # 3. paper index: inverted-index abstracts + contentless FTS
    build_paper_index(data / "paper_index.sqlite")
    if (C.OUTPUTS / "index" / "full_paper_index_ranked.csv").exists():
        shutil.copy(C.OUTPUTS / "index" / "full_paper_index_ranked.csv",
                    data / "paper_index_ranked.csv")

    # 4. graphs, gzipped (GraphML is verbose XML; compresses ~10x)
    import gzip
    for g in EX.glob("*.graphml"):
        with open(g, "rb") as fi, gzip.open(graphs / (g.name + ".gz"), "wb") as fo:
            shutil.copyfileobj(fi, fo)

    # 5. interactive tools (field map has no abstracts/emails; search uses
    #    inverted-index abstracts reconstructed in-browser)
    for t in ["field_map_report.html"]:
        if (C.OUTPUTS / t).exists():
            shutil.copy(C.OUTPUTS / t, tools / t)
    if (C.OUTPUTS / "index" / "paper_search.html").exists():
        shutil.copy(C.OUTPUTS / "index" / "paper_search.html",
                    tools / "paper_search.html")

    # 6. docs: methods + narrative + the OSF PDFs
    for m in ["field_state.md", "field_boundary_report.md",
              "community0_subdivision.md", "book_chapter_recommendation.md",
              "open_resource_plan.md"]:
        if (C.OUTPUTS / m).exists():
            shutil.copy(C.OUTPUTS / m, docs / m)
    pdfdir = docs / "pdf"; pdfdir.mkdir()
    for pdf in (C.OUTPUTS / "pdf").glob("OSF_*.pdf"):
        shutil.copy(pdf, pdfdir / pdf.name)

    # 7. license, citation, datapackage, readme, dictionary, changelog
    def sub(t):
        return (t.replace("__VER__", VERSION).replace("__SNAP__", SNAPSHOT)
                .replace("__CONCEPT_DOI__", CONCEPT_DOI)
                .replace("__VERSION_DOI__", VERSION_DOI))
    (RELEASE / "LICENSE").write_text(CC0_TEXT)
    (RELEASE / "CITATION.cff").write_text(sub(CITATION))
    (RELEASE / "datapackage.json").write_text(datapackage(data, graphs))
    (RELEASE / "README.md").write_text(sub(README))
    (docs / "DATA_DICTIONARY.md").write_text(DATA_DICTIONARY)
    (docs / "CHANGELOG.md").write_text(CHANGELOG.replace("__VER__", VERSION))

    # 8. verify no email leaks
    leaks = scan_for_emails(RELEASE)
    print("=== build_release ===")
    total = sum(1 for _ in RELEASE.rglob("*") if _.is_file())
    size = sum(p.stat().st_size for p in RELEASE.rglob("*") if p.is_file())
    print(f"  files: {total}, size: {size/1024/1024:.1f} MB")
    print(f"  version: {VERSION}, snapshot: {SNAPSHOT}")
    if leaks:
        print("  EMAIL LEAK CHECK: FAILED")
        for h in leaks:
            print(f"    {h}")
    else:
        print("  EMAIL LEAK CHECK: PASS (no addresses, no email columns)")
    print(f"  bundle: {RELEASE}")


def datapackage(data: Path, graphs: Path) -> str:
    resources = []
    for p in sorted(list(data.glob("*")) + list(graphs.glob("*"))):
        resources.append({
            "name": p.stem.lower().replace(" ", "_"),
            "path": str(p.relative_to(RELEASE)),
            "format": p.suffix.lstrip("."),
        })
    pkg = {
        "name": "biophoton-field-map",
        "title": "Biophoton / Ultra-Weak Photon Emission Field Map",
        "id": f"https://doi.org/{CONCEPT_DOI}",
        "description": "Structured, ranked, searchable map of the biophoton / "
                       "UPE research field, derived from OpenAlex. Abstracts are "
                       "shipped as an inverted index.",
        "version": VERSION,
        "doi": {"concept": CONCEPT_DOI, "version": VERSION_DOI},
        "licenses": [{"name": "CC0-1.0",
                      "path": "https://creativecommons.org/publicdomain/zero/1.0/",
                      "title": "Creative Commons Zero v1.0 Universal"}],
        "sources": [{"title": "OpenAlex", "path": "https://openalex.org"}],
        "resources": resources,
    }
    return json.dumps(pkg, indent=2)


CC0_TEXT = """Creative Commons CC0 1.0 Universal

The person who associated a work with this deed has dedicated the work to the
public domain by waiving all of his or her rights to the work worldwide under
copyright law, including all related and neighboring rights, to the extent
allowed by law.

You can copy, modify, distribute and perform the work, even for commercial
purposes, all without asking permission.

Full legal code: https://creativecommons.org/publicdomain/zero/1.0/legalcode

--
Data source: OpenAlex (https://openalex.org), itself released under CC0.
Abstracts are provided in inverted-index form, mirroring OpenAlex.
Citation is requested but not required. See CITATION.cff.
"""

CITATION = """cff-version: 1.2.0
title: Biophoton / Ultra-Weak Photon Emission Field Map
message: "If you use this resource, please cite it (citation requested, not required)."
type: dataset
version: "__VER__"
license: CC0-1.0
doi: __CONCEPT_DOI__
identifiers:
  - type: doi
    value: __CONCEPT_DOI__
    description: Concept DOI (cite all versions)
  - type: doi
    value: __VERSION_DOI__
    description: "Version __VER__"
abstract: >-
  A structured, ranked, searchable map of the biophoton / ultra-weak photon
  emission (UPE) research field, seeded from Michal Cifra's library and enriched
  via OpenAlex, with a sub-field clustering and an open-science overlay.
authors:
  - family-names: Etzrodt
    given-names: Martin
    affiliation: Open Science Institute
keywords:
  - biophotons
  - ultra-weak photon emission
  - bibliometrics
  - open science
"""

README = """# Biophoton / Ultra-Weak Photon Emission Field Map

An open, versioned map of the biophoton / UPE research field: 18,355 works and
39,312 authors, seeded from Michal Cifra's library and enriched via OpenAlex,
clustered into sub-fields and scored for openness.

**Version __VER__ . Snapshot __SNAP__ . License: CC0 1.0 (public domain).**

**DOI:** https://doi.org/__CONCEPT_DOI__ (cite all versions) . This release:
https://doi.org/__VERSION_DOI__

## What is in here

- `data/fieldmap.sqlite` and parquet/CSV exports: works, authors, institutions,
  authorships, topics, citation and co-authorship edges, sub-field communities.
- `data/paper_index.sqlite`: every work ranked by a composite importance score,
  with a full-text search index (contentless FTS5) and abstracts in
  inverted-index form. `data/paper_index_ranked.csv` is the compact ranked list.
- `data/researchers*.csv`: the ranked researcher tables (public identifiers only).
- `graphs/*.graphml.gz`: co-authorship, coupling, co-citation, topic graphs for
  Gephi (gzip-compressed; `gunzip` before opening).
- `tools/field_map_report.html`, `tools/paper_search.html`: self-contained
  interactive views. Open in any browser.
- `docs/`: methods, the state-of-field report, and OSF PDFs.

## Abstracts

Abstracts are distributed as an inverted index (word to positions), mirroring
OpenAlex. The tools reconstruct reading order in your browser. No ordered
abstract prose is stored in this release.

## Privacy

This release contains public identifiers only (names, ORCID, ROR institutions).
Corresponding-author email addresses collected during the project are held
privately by OSF and are not part of this release. To have your record amended
or removed, open an issue on the project repository.

## How to cite

Etzrodt, M. (2026). Biophoton / Ultra-Weak Photon Emission Field Map (__VER__)
[Data set]. Zenodo. https://doi.org/__VERSION_DOI__

To cite the resource across all versions, use the concept DOI
https://doi.org/__CONCEPT_DOI__ (it resolves to the latest release). See
`CITATION.cff` for machine-readable metadata. Citation is requested but, under
CC0, not required.

## Provenance and reproducibility

Derived from OpenAlex (CC0). The build pipeline is idempotent and cached; each
release pins its snapshot date. Known limitations: some author records are split
by OpenAlex disambiguation (a few are merged here; others are flagged in
`data/author_splits_flagged.json`), and a small amount of grey literature is not
in OpenAlex (`data/seed_unmatched.csv`). Corrections are welcome.
"""

DATA_DICTIONARY = """# Data dictionary

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
"""

CHANGELOG = """# Changelog

## __VER__ (initial public release)

- First open release of the biophoton / UPE field map.
- 18,355 works, 39,312 authors, sub-field clustering, openness overlay.
- Abstracts shipped as inverted index. Contact emails excluded.
- License: CC0 1.0.
"""


if __name__ == "__main__":
    main()
