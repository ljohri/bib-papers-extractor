# PDF acquisition policy

## Principle

This tool downloads **only publicly available, open-access** PDFs. It does **not**
bypass paywalls, scrape Sci-Hub, evade CAPTCHAs, harvest credentials, or impersonate
authenticated sessions.

## Allowed sources

- **arXiv** — direct `arxiv.org/pdf/{id}.pdf`
- **Unpaywall OA locations** — only entries where `is_oa = true` and `host_type ≠ paywalled`
- **OpenAlex OA locations** — `open_access`, `primary_location`, and entries in `locations`
  marked OA
- **Semantic Scholar** — `openAccessPdf.url` field
- **Publisher OA links** — when explicitly tagged OA in resolver metadata
- **Institutional repositories** discovered via Unpaywall / OpenAlex (e.g. preprint
  servers, university repositories)

## Denied sources

The following are **rejected on sight**:

- Sci-Hub (any TLD), LibGen, Library Genesis, Library.lol
- Z-Library, Anna's Archive, paywall-bypass mirrors
- URLs requiring login, cookies, captcha, or institutional proxy
- Non-`https://` URLs (we do not fetch over plain HTTP)
- URLs whose host or path matches the deny-fragment list in `license_policy.py`

## Validation pipeline

After a candidate is approved by `license_policy.py` and downloaded:

1. **Content-Type** must be `application/pdf` (or `application/octet-stream` with a
   `.pdf` URL path).
2. The first **5 bytes** of the response body must equal `%PDF-` (the PDF magic number).
3. If the response is HTML, it is rejected and the candidate is moved to the
   "skipped" section of the manifest with `reason = "non_pdf_response"`.

## Filenames

Deterministic filename pattern:

```
YEAR_FirstAuthor_ShortTitle_DOIHash.pdf
```

Example: `2017_Vaswani_AttentionIsAllYouNeed_a1b2c3.pdf`

- `YEAR` from resolved metadata; `0000` if unknown.
- `FirstAuthor` is the first author's family name, ASCII-folded, max 24 chars.
- `ShortTitle` is the first 4 title words, CamelCased, ASCII-only.
- `DOIHash` is the first 6 hex chars of `sha256(doi || arxiv_id || url)` for uniqueness.

## Audit logging

Every accept/reject decision is recorded in the run manifest with:

- `reference_id`, `url`, `source`, `decision`, `reason`
- License string when known (e.g. `cc-by-4.0`, `arxiv-nonexclusive`)
