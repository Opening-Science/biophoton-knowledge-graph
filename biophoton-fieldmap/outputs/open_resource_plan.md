# Open Resource Release Plan

## Purpose

This plan sets out how to release the biophoton and ultra-weak photon emission
(UPE) field map as an open, living community resource. The field map already
covers 18,355 works and 39,312 authors, is reproducible from a cached pipeline,
and ships interactive tools as self-contained HTML. The remaining work is
packaging, privacy, licensing, hosting, and governance, not new analysis.

## Decisions locked

- **License: CC0.** The derived bibliometric metadata is released into the public
  domain, matching the CC0 license of the underlying OpenAlex data. A citation
  request accompanies the release, but reuse carries no legal conditions.
- **Abstracts: inverted index.** Abstracts are distributed in the OpenAlex
  inverted-index form rather than as reconstructed prose. This mirrors OpenAlex
  and removes the copyright question. The tools reconstruct abstracts locally for
  search and display, so functionality is preserved.
- **Maintenance: living resource.** The resource is published as versioned
  releases on a recurring refresh, with a corrections channel and a named
  maintainer, rather than as a single frozen snapshot.

## What is released, and what is held back

Everything is public except the contact-email data, which stays internal to OSF
under the legitimate-interest basis recorded in the data ethics note.

Released openly:

- The field database (SQLite, plus parquet and CSV of every table).
- The full ranked paper index with a full-text search index.
- The researcher table with the email column removed, keeping only public
  identifiers (ORCID and ROR institution).
- The four network graphs for Gephi.
- The interactive field map and paper search pages.
- The state-of-field report, the OSF PDFs, and the methods documentation.
- The pipeline source code.

Held back, internal to OSF:

- The corresponding-author email column and the PDF fetch log.
- Downloaded open-access PDFs, since redistribution rights vary by publisher.
- The OpenAlex API key.

A release script enforces the split. The public bundle is produced by code, not
by hand, so no email can leak by accident.

## Attribution

CC0 requests, but does not require, citation. The release credits OpenAlex for
the source data, ORCID and ROR for identifiers, and Michal Cifra's seed library
for the field anchor. A CITATION.cff file and a concept DOI make the resource
citable in one line.

## Packaging

The release ships in three layers so different users are served.

- **Archival data package.** SQLite, parquet, CSV, and GraphML, with a data
  dictionary documenting every table and column, and a machine-readable
  datapackage descriptor for discovery.
- **Interactive layer.** The field-map report and the paper-search page, already
  self-contained static HTML.
- **Reproducibility layer.** The pinned pipeline, a pinned requirements file, the
  OpenAlex snapshot date, and the citation metadata.

## Hosting and distribution

All components are free and standard for open science.

- **Zenodo** mints a DOI for each versioned release. This is the citable,
  permanent anchor.
- **GitHub** holds the pipeline code and the issue tracker, which doubles as the
  corrections channel, and serves the interactive HTML through GitHub Pages at no
  cost, since the tools are already static.
- **The OSF project page** provides the branded institutional home, aligned with
  the Foundation mission.
- Registration with a research-data registry adds discoverability.

## Reproducibility and the refresh cycle

The on-disk cache makes any run byte-reproducible from the pinned snapshot date.
Releases follow semantic versions under a single concept DOI, with a changelog.
The pipeline re-runs cheaply, on the order of two thousand OpenAlex calls on a
free key, so a biannual refresh keeps the resource current. Each refresh is a new
versioned release produced by the same scripted path: harvest, strip the private
columns, package, publish.

## Governance and community contribution

Governance is what turns a data package into a resource.

- **Steward.** OSF and OSI provide the institutional home. A named maintainer
  owns the refresh and the issue queue.
- **Corrections.** A public channel handles the two known weak spots: author
  disambiguation errors of the Van Wijk and Popp kind, and missing grey
  literature such as the eighteen unmatched seeds, patents, and theses.
  Contributions from the field are realistic and improve quality.
- **Opt-out.** A documented route lets any researcher have their row amended or
  removed, honoring the ethics basis.
- **Advisory input.** The openness overlay already identifies who builds in the
  open. Those researchers are the natural first reviewers and endorsers.

## Launch and outreach

A short data descriptor, most of which already exists in the state-of-field
report, is posted as a preprint. Posting a preprint is itself an open-science act
consistent with the book thesis. The mapped community is reached through the
public routing already built, and at the venues the map identifies. The book
becomes both a product of the resource and its advertisement.

## Roadmap

1. **Release preparation.** Write the release and privacy-strip script, the data
   dictionary, the citation metadata, the data package descriptor, and the
   license files. Convert abstracts to inverted-index form for the public bundle.
2. **Publish version one.** Zenodo DOI, GitHub repository, GitHub Pages for the
   interactive tools, and the OSF project page.
3. **Governance live.** Corrections and opt-out channels open, maintainer named.
4. **Announce.** Preprint and outreach to the field.
5. **Sustain.** Scheduled refresh and versioned re-releases.

## Immediate next steps

- Produce the public release bundle locally, so it is ready to upload. This is
  code we can write now: strip the email column, convert abstracts to inverted
  index, add the license, data dictionary, citation file, and package descriptor.
- Name a maintainer and create the OSF project shell.
- Reserve the Zenodo concept DOI and the GitHub repository.
