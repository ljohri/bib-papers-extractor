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

- `tenacity` exponential backoff (2s base, 6 attempts) for 5xx/429/network errors.
- `aiolimiter` bounds per-API requests-per-second.
- Global concurrency capped by `MAX_CONCURRENT_REQUESTS`.

## Caching

Every API response is cached in SQLite (`api_cache(source, key, payload, expires_at)`).
TTLs: Crossref/OpenAlex/S2 metadata = 30 days, arXiv = 7 days, Unpaywall = 30 days.
