"""Watch Cifra's public Zotero library for changes (CI-friendly).

Runs weekly in GitHub Actions (.github/workflows/zotero-watch.yml) and can
be run locally. Standard library only, no pipeline data needed: it keeps a
tracked snapshot of Zotero group 2260466 (the biophotoniq.net literature
list) and reports what changed since the last run.

This is deliberately the shallow half of the tooling: it detects and
reports. The deep half -- cross-referencing against the field-map universe
and fetching PDFs -- is collect_zotero_library.py, which needs the local
data and is run by hand after the watcher flags additions.

Tracked outputs (committed by the workflow when they change):
  literature/zotero_watch.csv   current snapshot, newest first
  literature/ZOTERO_WATCH.md    latest delta report, human-readable

When run inside GitHub Actions, writes `changed` and `new_count` to
GITHUB_OUTPUT so the workflow can decide whether to commit / open an issue.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

GROUP = "2260466"
API = f"https://api.zotero.org/groups/{GROUP}/items/top"
ROOT = Path(__file__).resolve().parent.parent.parent
SNAPSHOT = ROOT / "literature" / "zotero_watch.csv"
REPORT = ROOT / "literature" / "ZOTERO_WATCH.md"
UA = "biophoton-knowledge-graph zotero-watch (github.com/Opening-Science)"

FIELDS = ["zotero_key", "date_added", "item_type", "year", "first_author",
          "title", "journal", "doi", "url"]


def fetch_json(url: str) -> tuple[list, dict]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode()), dict(r.headers)


def pull() -> tuple[list[dict], str]:
    items, start, version = [], 0, ""
    while True:
        batch, headers = fetch_json(f"{API}?format=json&limit=100&start={start}")
        version = headers.get("Last-Modified-Version", version)
        if not batch:
            break
        items.extend(batch)
        if len(batch) < 100:
            break
        start += 100
        time.sleep(0.5)
    return items, version


def flatten(items: list[dict]) -> list[dict]:
    rows = []
    for it in items:
        d = it.get("data", {})
        creators = d.get("creators") or []
        first = next((c.get("lastName") or c.get("name") or ""
                      for c in creators), "")
        m = re.search(r"\b(1[89]\d{2}|20\d{2})\b", d.get("date") or "")
        doi = (d.get("DOI") or "").strip().lower()
        doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
        rows.append({
            "zotero_key": d.get("key", ""),
            "date_added": d.get("dateAdded", ""),
            "item_type": d.get("itemType", ""),
            "year": m.group(1) if m else "",
            "first_author": first,
            "title": (d.get("title") or "")[:300],
            "journal": d.get("publicationTitle") or d.get("bookTitle") or "",
            "doi": doi if doi.startswith("10.") else "",
            "url": d.get("url") or "",
        })
    rows.sort(key=lambda r: r["date_added"], reverse=True)
    return rows


def read_snapshot() -> dict[str, dict]:
    if not SNAPSHOT.exists():
        return {}
    with open(SNAPSHOT, encoding="utf-8") as f:
        return {r["zotero_key"]: r for r in csv.DictReader(f)}


def write_snapshot(rows: list[dict]) -> None:
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, quoting=csv.QUOTE_MINIMAL)
    w.writeheader()
    w.writerows(rows)
    SNAPSHOT.write_text(buf.getvalue())


def cite(r: dict) -> str:
    bits = [b for b in (r["first_author"], r["year"]) if b]
    head = " ".join(bits)
    doi = f" — doi:[{r['doi']}](https://doi.org/{r['doi']})" if r["doi"] else ""
    return f"**{r['title']}**  \n  {head} · {r['item_type']}{doi}"


def write_report(new: list[dict], removed: list[dict], total: int,
                 version: str) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = ["# Zotero library watch — Cifra / biophotoniq group 2260466\n",
         f"_Last checked {now} · library version {version} · "
         f"{total} top-level items._\n",
         "The field's maintained bibliography, watched weekly by CI "
         "(`.github/workflows/zotero-watch.yml`). When items appear here, "
         "run `collect_zotero_library.py --download` locally to "
         "cross-reference and fetch them, and consider a seed refresh if "
         "additions accumulate.\n"]
    if new:
        L.append(f"## New since last check ({len(new)})\n")
        for r in new[:50]:
            L.append(f"- {cite(r)}")
        if len(new) > 50:
            L.append(f"- … and {len(new) - 50} more (see snapshot)")
        L.append("")
    if removed:
        L.append(f"## Removed since last check ({len(removed)})\n")
        for r in removed[:20]:
            L.append(f"- {cite(r)}")
        L.append("")
    if not new and not removed:
        L.append("_No changes since the previous check._\n")
    REPORT.write_text("\n".join(L))


def gh_output(**kv: str) -> None:
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            for k, v in kv.items():
                f.write(f"{k}={v}\n")


def main() -> int:
    old = read_snapshot()
    items, version = pull()
    rows = flatten(items)
    cur = {r["zotero_key"]: r for r in rows}

    new = [r for k, r in cur.items() if k not in old]
    removed = [r for k, r in old.items() if k not in cur]
    changed = bool(new or removed) or not SNAPSHOT.exists()

    write_snapshot(rows)
    write_report(new, removed, len(rows), version)

    print(f"library: {len(rows)} items (v{version}); "
          f"new: {len(new)}, removed: {len(removed)}")
    for r in new[:10]:
        print(f"  + {r['year']} {r['first_author']}: {r['title'][:70]}")
    gh_output(changed=str(changed).lower(), new_count=str(len(new)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
