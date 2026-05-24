# API resolution strategy

## Resolver precedence

For each `Reference` we try resolvers in this order, short-circuiting on a high-confidence hit:

```
DOI exact match              → 1.00
↓ (if no DOI)
arXiv ID exact match         → 0.98
↓
OpenAlex title (+ year/authors) match
↓
Crossref title (+ year/authors) match
↓
Semantic Scholar title match
↓
unresolved
```

## Confidence scoring

```
DOI exact match                              1.00
arXiv exact match                            0.98
title exact + year match                     0.93
high fuzzy title (≥92) + author overlap      0.85
title-only match                            ≤0.75
```

Components:

- **Title score** — `rapidfuzz.fuzz.token_set_ratio` on normalized titles (lowercase,
  whitespace-collapsed, punctuation-stripped).
- **Author overlap** — Jaccard of normalized last-name sets.
- **Year proximity** — exact match boosts; `±1` neutral; further apart penalized.
- **Source bonus** — DOI/arXiv exact > OpenAlex > Crossref > Semantic Scholar.

Final score is clamped to `[0, 1]`. Below `AUTO_DOWNLOAD_CONFIDENCE_THRESHOLD`
(default `0.80`) the reference is logged under "Low Confidence Matches" in the report
and **not** auto-downloaded.

## Strategies

| Strategy   | Behavior |
|---|---|
| `fast`     | Stop at first resolver hit ≥ 0.93 |
| `balanced` | Run DOI/arXiv first; if no high-confidence hit, query OpenAlex + Crossref and pick best |
| `deep`     | Always query all four resolvers and re-rank candidates |

## Politeness

- All clients send `User-Agent: bibpdf-mcp/...`.
- Crossref requests include `mailto=$CROSSREF_MAILTO` (polite pool).
- Unpaywall requires `email=$UNPAYWALL_EMAIL`.
- Semantic Scholar API key (if provided) raises rate limit.

## Retries & rate limits

- `tenacity` exponential backoff (4 attempts, 1.5x multiplier, capped at 20s) for 5xx/429/network errors.
- **`Retry-After` honored** — when an API returns `429` (or any retryable status) with a `Retry-After` header, we sleep that long (delta-seconds or HTTP-date, capped at 60s) before tenacity's next attempt.
- `aiolimiter` bounds per-API requests-per-second.
- Global concurrency capped by `MAX_CONCURRENT_REQUESTS`.

## Caching

Every API response is cached in SQLite (`api_cache(source, key, payload, expires_at)`).
TTLs: Crossref/OpenAlex/S2 metadata = 30 days, arXiv = 7 days, Unpaywall = 30 days.

## Semantic Scholar — endpoints and compliance

The Semantic Scholar resolver exposes all six paper-graph endpoints (all
usable unauthenticated):

| Method | Path                                | Resolver method   |
|--------|-------------------------------------|-------------------|
| GET    | `/graph/v1/paper/search`            | `search_papers`   |
| GET    | `/graph/v1/paper/search/bulk`       | `search_bulk`     |
| GET    | `/graph/v1/paper/{paper_id}`        | `lookup_paper`    |
| POST   | `/graph/v1/paper/batch`             | `batch_lookup`    |
| GET    | `/graph/v1/paper/{paper_id}/references` | `get_references` |
| GET    | `/graph/v1/paper/{paper_id}/citations`  | `get_citations`  |

`{paper_id}` accepts the canonical S2 paperId, `DOI:<doi>`, `arXiv:<id>`, and the
other prefixes documented by Semantic Scholar.

Compliance with the unauthenticated-access policy:

- **Daily budget 500–2,000 requests** — well within reach because every call
  is cached locally. A typical paper with ~30 references resolves in under
  100 requests on a fresh cache and ~zero on a warm cache.
- **Maximum 1 request/second** — enforced by an `aiolimiter.AsyncLimiter` set
  to `max_rate=1.0, time_period=1.0` whenever `SEMANTIC_SCHOLAR_API_KEY` is
  empty. Setting the key bumps the limit to 9 r/s.
- **Cache results** — the SQLite read-through cache keys every request by
  source / operation / id, with a 30-day TTL.
- **De-duplicate by DOI / S2 paperId / arXiv id** — both at the input level
  (`batch_lookup` normalizes ids before POSTing) and the output level
  (`dedupe_papers([...])` collapses records that share any one of those
  identifiers).
- **Exponential backoff with `Retry-After` handling** — see "Retries & rate
  limits" above. On 429, the `Retry-After` header (delta-seconds or
  HTTP-date) is honored before tenacity's exponential schedule kicks in.
