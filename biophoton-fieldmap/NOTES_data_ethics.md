# Data ethics — contact information (INTERNAL to OSF)

## Basis and scope
Contact data here is academic contact information the researchers **self-published**
in their own open-access papers (corresponding-author emails) or on open
infrastructure (ORCID, institutional/ROR profiles). Processing basis: legitimate
interest for scholarly outreach about the state of the biophoton/UPE field.

## Rules
- **Never published in the open book/dataset.** The `email` column in
  `contacts.csv` / `researchers.csv` is INTERNAL. Strip it before any public
  release; publish only name, ORCID, institution, and public profile URLs.
- **Provenance kept per email:** `email_source_doi`, `email_confidence`,
  `retrieved_date`. Every email traces to the specific paper it came from.
- **No guessing / no brute force:** emails are only taken verbatim from a PDF the
  researcher authored; none are inferred from name+domain patterns.
- **Honor opt-outs:** on any request, delete the person's row and record the
  opt-out.
- **Bounded collection:** only top-ranked targets, only recent
  corresponding-authored OA works, capped per author (see config.py).

## Provenance of the fetch
See `data/exports/contacts_fetch_log.json` for every PDF URL fetched and whether
an email was extracted.
