"""Central configuration for the biophoton fieldmap pipeline.

Everything tunable lives here so a rerun is fully reproducible and no cap or
threshold is buried in the middle of a stage.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- identity / OpenAlex auth --------------------------------------------
# As of early 2026 OpenAlex uses usage-based pricing with API keys.
#   - no key : $0.10/day (~1,000 list calls)
#   - free key: $1/day  (~10,000 list calls) -- get one at openalex.org/settings/api
# The key is read from the OPENALEX_API_KEY env var, or from a `.openalex_key`
# file in the repo root (gitignored). mailto is still sent as courtesy/id, and
# resolves the same way (OPENALEX_MAILTO env var, then a gitignored
# `.openalex_mailto` file) so no personal address is committed.
OPENALEX_BASE = "https://api.openalex.org"
DEFAULT_MAILTO = "office@opening.science"


def _load_local(env_var: str, filename: str) -> str | None:
    val = os.environ.get(env_var, "").strip()
    if val:
        return val
    f = Path(__file__).resolve().parent.parent / filename
    if f.exists():
        v = f.read_text().strip()
        if v:
            return v
    return None


API_KEY = _load_local("OPENALEX_API_KEY", ".openalex_key")
MAILTO = _load_local("OPENALEX_MAILTO", ".openalex_mailto") or DEFAULT_MAILTO

# --- paths ---------------------------------------------------------------
SRC_DIR = Path(__file__).resolve().parent
ROOT = SRC_DIR.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
CACHE = DATA / "cache"
DB_DIR = DATA / "db"
EXPORTS = DATA / "exports"
OUTPUTS = ROOT / "outputs"

SEEDS_CSV = RAW / "cifra_seeds.csv"
DB_PATH = DB_DIR / "fieldmap.sqlite"
RUN_LOG = ROOT / "run_log.md"

for _d in (RAW, CACHE, DB_DIR, EXPORTS, OUTPUTS):
    _d.mkdir(parents=True, exist_ok=True)

# --- OpenAlex request tuning ---------------------------------------------
# Fields to select on works to keep payloads small (spec §4 Stage A).
WORK_SELECT = (
    "id,doi,title,publication_year,type,cited_by_count,authorships,"
    "primary_topic,topics,concepts,referenced_works,related_works,"
    "open_access,primary_location,locations,corresponding_author_ids,language"
)
AUTHOR_SELECT = (
    "id,display_name,orcid,works_count,cited_by_count,"
    "summary_stats,last_known_institutions,affiliations"
)
PER_PAGE = 200          # OpenAlex max
SLEEP_BETWEEN = 0.20    # polite pacing (~5 req/s, comfortably under the ceiling)
MAX_RETRIES = 8
RETRY_MAX_WAIT = 120    # cap on exponential backoff between retries (s)
TIMEOUT = 40.0

# --- harvest caps / prune thresholds (spec §3, §4) -----------------------
HARD_CAP_WORKS = 40_000         # global ceiling on the works universe
FORWARD_CITE_CAP_PER_SEED = 500  # cap forward-cites for hyper-cited seeds
# A hyper-cited seed is one whose cited_by_count exceeds this; its forward
# citations are capped to the top FORWARD_CITE_CAP_PER_SEED by cited_by_count.
HYPER_CITED_THRESHOLD = 1_000

HOP1_MIN_LINKS = 2   # keep a hop-1 candidate iff it links to >=2 seeds
HOP2_MIN_LINKS = 3   # stricter for the noisier hop-2 ring

# Forward-citation volume cap PER BATCH of 50 sources (spec: cap forward-cites
# by top cited_by_count). Batched cites queries are sorted cited_by_count:desc
# and truncated here, so a batch containing hyper-cited works cannot page its
# entire (100k+) citing set. 3000 = ~15 pages/batch.
FORWARD_MAX_WORKS_PER_BATCH = 3000

# --- seed matching -------------------------------------------------------
FUZZY_TITLE_MIN = 90   # rapidfuzz token_set_ratio threshold
YEAR_TOLERANCE = 1     # +/- years for a title match to count
DOI_BATCH = 50         # DOIs per batched works request

# --- contacts (Stage F) --------------------------------------------------
# Email-from-OA-PDF extraction is bounded: only the top-ranked targets, only
# their recent corresponding-authored OA works, capped per author. Emails are
# self-published by the authors in their own papers; provenance is kept and the
# email column is never published in the open dataset (see NOTES_data_ethics.md).
CONTACTS_MAX_TARGETS = 250       # top-N researchers to attempt email extraction
CONTACTS_CORE_TARGETS = 120      # additionally attempt the biophoton-core top-N
CONTACTS_MAX_PDF_PER_AUTHOR = 3  # recent corresponding OA works per target
CONTACTS_ROUTING_TOP_N = 500     # researchers to build ORCID/inst routing for
CONTACTS_RECENT_YEAR = 2015      # "recent" corresponding works from this year

# --- core biophoton topical anchors (for topical_fit / labeling) ---------
# Lowercased substrings that mark the biophoton/UPE core in topic names.
CORE_TOPIC_HINTS = (
    "photon", "luminescence", "chemiluminescence", "bioluminescence",
    "reactive oxygen", "oxidative", "free radical", "biophoton",
)
