"""Collect Cifra's public Zotero library (biophotoniq.net literature list).

The literature browser on biophotoniq.net/en/science.html is a front-end to
the public Zotero group 2260466 ("biophotons"), currently 381 top-level
items. That library is the field's live, curated bibliography -- the
cifra_seeds.csv snapshot this project was seeded from, but maintained. This
stage pulls it via the documented Zotero API, cross-references every entry
against the universe and the harvested corpus, and (with --download) fetches
the open-access PDFs we do not yet hold.

Cross-reference logic: DOI first (normalised), then title fuzzy-match
(rapidfuzz, >=93) for the entries without a DOI. Every item gets a status:

  harvested        already on disk in literature/papers/
  in-universe      known to the field map but no PDF held
  new-to-universe  in Cifra's library but not in the 18,355-work map --
                   candidates for a future seed refresh

Outputs:
  literature/zotero_library.csv   the 381 items, cross-referenced
  literature/papers/              --download adds missing OA PDFs, named
                                  <year>_<Author>_<workid-or-zotkey>.pdf
  harvest log entries             appended, same journal as the main harvest

Usage:
  python collect_zotero_library.py             # pull + cross-reference
  python collect_zotero_library.py --download  # ...and fetch missing OA PDFs
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
from pathlib import Path

import httpx
import pandas as pd
from rapidfuzz import fuzz

import config as C
from harvest_oa_pdfs import (LOG_PATH, MIN_PDF_BYTES, PAPERS, fetch,
                             log_attempt, mine_html, rewrite, slug,
                             unpaywall_pdf)

GROUP = "2260466"
API = f"https://api.zotero.org/groups/{GROUP}/items/top"
ZCACHE = C.CACHE / "zotero"
OUT_CSV = C.ROOT.parent / "literature" / "zotero_library.csv"
CLOSED_MD = C.ROOT.parent / "literature" / "zotero_closed_access.md"

FUZZ_THRESHOLD = 93


def norm_doi(d: str) -> str:
    d = (d or "").strip().lower()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
    return d if d.startswith("10.") else ""


def norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def pull_items(client: httpx.Client) -> list[dict]:
    """All top-level items, cached one page per file."""
    ZCACHE.mkdir(parents=True, exist_ok=True)
    items, start = [], 0
    while True:
        page = ZCACHE / f"top_{start}.json"
        if page.exists():
            batch = json.loads(page.read_text())
        else:
            r = client.get(API, params={"format": "json", "limit": 100,
                                        "start": start})
            r.raise_for_status()
            batch = r.json()
            page.write_text(json.dumps(batch))
            time.sleep(0.5)
        if not batch:
            break
        items.extend(batch)
        if len(batch) < 100:
            break
        start += 100
    return items


def flatten(items: list[dict]) -> pd.DataFrame:
    rows = []
    for it in items:
        d = it.get("data", {})
        creators = d.get("creators") or []
        authors = "; ".join(
            f"{c.get('lastName', c.get('name', ''))}".strip()
            for c in creators if c.get("creatorType") in ("author", "editor"))
        first = next((c.get("lastName") or c.get("name") or ""
                      for c in creators), "")
        year = ""
        m = re.search(r"\b(1[89]\d{2}|20\d{2})\b", d.get("date") or "")
        if m:
            year = m.group(1)
        rows.append({
            "zotero_key": d.get("key", ""),
            "item_type": d.get("itemType", ""),
            "year": year,
            "first_author": first,
            "authors": authors[:300],
            "title": (d.get("title") or "")[:300],
            "journal": d.get("publicationTitle") or d.get("bookTitle") or "",
            "doi": norm_doi(d.get("DOI") or ""),
            "url": d.get("url") or "",
        })
    return pd.DataFrame(rows)


def cross_reference(z: pd.DataFrame) -> pd.DataFrame:
    w = pd.read_parquet(C.EXPORTS / "works.parquet")
    w["d"] = w["doi"].fillna("").map(norm_doi)
    by_doi = w[w["d"] != ""].set_index("d")
    manifest = pd.read_csv(C.ROOT.parent / "literature" / "manifest.csv")
    have = set(manifest[manifest["status"].isin(["ok", "have"])]["work_id"])
    # every PDF actually on disk, whatever stage put it there -- files are
    # named ..._<OpenAlex id>.pdf, or ..._<zotero key>.pdf for items the
    # universe does not know
    on_disk = {p.name.split("_")[-1].removesuffix(".pdf")
               for p in PAPERS.glob("*.pdf")}
    have |= {x for x in on_disk if x.startswith("W")}
    disk_zkeys = {x for x in on_disk if not x.startswith("W")}

    # title index for the no-DOI fallback
    wt = w[["work_id", "title", "is_seed"]].copy()
    wt["nt"] = wt["title"].fillna("").map(norm_title)
    wt = wt[wt["nt"].str.len() > 15]

    out = []
    for r in z.itertuples():
        wid, is_seed, how = "", 0, ""
        if r.doi and r.doi in by_doi.index:
            hit = by_doi.loc[[r.doi]].iloc[0]
            wid, is_seed, how = hit["work_id"], int(hit["is_seed"]), "doi"
        else:
            nt = norm_title(r.title)
            if len(nt) > 15:
                # cheap prefilter, then fuzzy
                cand = wt[wt["nt"].str.startswith(nt[:12])]
                if not len(cand):
                    cand = wt[wt["nt"].str.contains(
                        re.escape(nt[:25]), regex=True)]
                best, score = None, 0
                for c in cand.itertuples():
                    s = fuzz.ratio(nt, c.nt)
                    if s > score:
                        best, score = c, s
                if best is not None and score >= FUZZ_THRESHOLD:
                    wid, is_seed = best.work_id, int(best.is_seed)
                    how = f"title~{score:.0f}"
        if (wid and wid in have) or r.zotero_key in disk_zkeys:
            status = "harvested"
        elif wid:
            status = "in-universe"
        else:
            status = "new-to-universe"
        out.append({**r._asdict(), "work_id": wid, "is_seed": is_seed,
                    "match": how, "status": status})
    df = pd.DataFrame(out).drop(columns=["Index"])
    return df


def download_missing(z: pd.DataFrame, client: httpx.Client) -> pd.DataFrame:
    """Fetch OA PDFs for items not on disk, via the harvest resolver."""
    todo = z[z["status"] != "harvested"]
    print(f"download pass over {len(todo)} items without a held PDF")
    got = 0
    statuses = z["status"].copy()
    for i, r in enumerate(todo.itertuples()):
        name_id = r.work_id or r.zotero_key
        dest = PAPERS / (f"{r.year or '0000'}_{slug(r.first_author or 'Unknown')}"
                         f"_{name_id}.pdf")
        if dest.exists() and dest.stat().st_size >= MIN_PDF_BYTES:
            statuses.loc[r.Index] = "harvested"
            continue
        urls: list[str] = []
        if r.url and str(r.url).startswith("http") \
                and "doi.org" not in str(r.url):
            urls.append(str(r.url))
            urls += rewrite(str(r.url))
        if r.doi:
            if (u := unpaywall_pdf(client, r.doi)):
                urls.append(u)
            urls.append(f"https://doi.org/{r.doi}")
        tried = []
        for url in urls[:6]:
            res = fetch(client, url)
            tried.append(f"{url.split('/')[2]}:{res.reason}")
            if res.kind == "pdf":
                dest.write_bytes(res.data)
                statuses.loc[r.Index] = "harvested"
                log_attempt({"work_id": name_id, "status": "ok",
                             "file": dest.name, "bytes": len(res.data),
                             "url": url, "reason": "zotero-list"})
                got += 1
                break
            if res.kind == "html":
                for u in mine_html(res.html, res.final_url)[:2]:
                    if u not in urls:
                        urls.append(u)
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{len(todo)} attempted, {got} new PDFs")
    print(f"download pass: {got} new PDFs")
    return z.assign(status=statuses)


def closed_report(z: pd.DataFrame, client: httpx.Client) -> None:
    """The papers on Cifra's list no automated OA route can deliver.

    'Closed' per OpenAlex is re-verified against Unpaywall (cached) before a
    work is declared unobtainable -- OpenAlex OA flags go stale, and anything
    Unpaywall still knows an OA copy for belongs in the harvest queue, not on
    this list. What remains is the institutional-access / interlibrary-loan
    shopping list, pre-curated by the field's own bibliography.
    """
    w = pd.read_parquet(C.EXPORTS / "works.parquet")[
        ["work_id", "is_oa", "oa_status", "cited_by_count"]]
    m = z.merge(w, on="work_id", how="left")
    miss = m[m["status"] != "harvested"].copy()

    confirmed, recoverable = [], []
    for r in miss.itertuples():
        if r.doi and unpaywall_pdf(client, r.doi):
            recoverable.append(r)          # an OA copy exists after all
        elif pd.notna(r.is_oa) and r.is_oa == 1:
            recoverable.append(r)          # OpenAlex says OA; harvest retries
        else:
            confirmed.append(r)

    def row(r) -> str:
        yr = str(r.year)[:4] if str(r.year) != "nan" else "n.d."
        doi = f"[{r.doi}](https://doi.org/{r.doi})" if r.doi else "—"
        cites = (int(r.cited_by_count)
                 if pd.notna(getattr(r, "cited_by_count", None)) else "")
        wid = r.work_id or "not in universe"
        return (f"| {yr} | {str(r.first_author)[:22]} | "
                f"{str(r.title)[:95]} | {str(r.journal)[:40]} | "
                f"{doi} | {cites} | {wid} |")

    in_uni = [r for r in confirmed if r.work_id]
    outside = [r for r in confirmed if not r.work_id]
    in_uni.sort(key=lambda r: -(r.cited_by_count
                                if pd.notna(r.cited_by_count) else 0))
    outside.sort(key=lambda r: str(r.year), reverse=True)

    L = ["# Cifra's library: papers with no open-access route\n",
         "Entries from the biophotoniq Zotero library (group 2260466) that "
         "the corpus does not hold and that neither OpenAlex nor Unpaywall "
         "knows an open copy for. Obtaining these means institutional "
         "access, interlibrary loan, or asking the authors -- this file is "
         "that shopping list, regenerated by "
         "`collect_zotero_library.py`.\n",
         f"_{len(confirmed)} confirmed closed "
         f"({len(in_uni)} in the mapped universe, {len(outside)} outside "
         f"it) · {len(recoverable)} further misses still have a live OA "
         f"route and stay in the harvest queue._\n",
         f"## Confirmed closed, in the field map ({len(in_uni)})\n",
         "| Year | First author | Title | Journal | DOI | Cites | Work |",
         "|---|---|---|---|---|---:|---|"]
    L += [row(r) for r in in_uni]
    L += [f"\n## Confirmed closed, outside the mapped universe "
          f"({len(outside)})\n",
          "Mostly historical or grey literature (books, theses, patents, "
          "the Russian-school lineage) without DOIs.\n",
          "| Year | First author | Title | Journal | DOI | Cites | Work |",
          "|---|---|---|---|---|---:|---|"]
    L += [row(r) for r in outside]
    CLOSED_MD.write_text("\n".join(L) + "\n")
    print(f"  closed-access list: {len(confirmed)} confirmed "
          f"({len(recoverable)} misses still have an OA route) "
          f"-> {CLOSED_MD.name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    args = ap.parse_args()

    client = httpx.Client(
        timeout=60.0, follow_redirects=True,
        headers={"User-Agent": f"biophoton-fieldmap/1.0 (OSF field map; "
                               f"mailto:{C.MAILTO})"})
    items = pull_items(client)
    z = flatten(items)
    print(f"Zotero group {GROUP}: {len(z)} top-level items "
          f"({z['doi'].astype(bool).sum()} with DOI)")
    z = cross_reference(z)
    if args.download:
        z = download_missing(z, client)
    closed_report(z, client)
    client.close()

    z.to_csv(OUT_CSV, index=False, quoting=csv.QUOTE_MINIMAL)
    print("=== collect_zotero_library ===")
    print(z["status"].value_counts().to_string())
    seeds = int((z["is_seed"] == 1).sum())
    print(f"  already seeds of the map : {seeds}")
    print(f"  csv: {OUT_CSV}")


if __name__ == "__main__":
    main()
