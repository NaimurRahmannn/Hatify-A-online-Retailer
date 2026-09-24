# Hybrid Retrieval Engine Sprint 3.5 Design

## Purpose

Harden Haatify's completed Sprint 3 query-understanding and hybrid retrieval
flow for production use. Sprint 3.5 improves deterministic extraction,
PostgreSQL JSON filtering, provider lifecycle, query-analysis caching,
telemetry, timing visibility, and failure isolation without redesigning the
retrieval engine.

This sprint does not add RAG, chatbot behavior, conversational memory,
recommendations, or answer generation. It does not add brand or other fashion
attributes to the commerce `Product` model.

## Existing System and Findings

The current request flow is:

```text
POST /api/ai-search/
        |
        v
new QueryAnalyzer and Gemini client
        |
        v
rule extraction + LLM extraction
        |
        v
metadata queryset predicates
        |
        v
keyword and semantic retrieval
        |
        v
hybrid ranking and SearchQueryLog
```

The implementation has the following production gaps:

- LLM output is applied before deterministic data, so a plausible but
  inaccurate LLM value can replace an explicit price or category.
- Empty LLM lists can suppress useful rule output.
- color, size, category, brand, and gender filters use substring matching on
  JSON values; an exact color such as `black` can therefore match unrelated
  text such as `blackberry`.
- every request constructs a new analyzer, Gemini provider, and Gemini client.
- repeated normalized queries always call the provider.
- query telemetry lacks cache state and performance timings.
- query-log writes are on the successful response path and are not isolated
  from database failures.
- the existing SQLite test setup cannot create the PostgreSQL/pgvector search
  schema, so PostgreSQL-specific behavior needs an explicit test strategy.

The current implementation already has two useful fallbacks that remain:
Gemini analysis failure falls back to rule extraction, and semantic retrieval
failure falls back to keyword retrieval.

## Target Architecture

```text
User Query
    |
    v
normalize query
    |
    v
query-analysis cache lookup
    | hit                 | miss
    |                     v
    |             reusable QueryAnalyzer
    |                     |
    |             rules + Gemini merge
    |                     |
    +<---------- cache validated analysis
    |
    v
exact metadata filters
    |
    v
keyword retrieval + semantic retrieval
    |
    v
hybrid ranking
    |
    v
safe analytics write + API response
```

The existing analyzer, filter, retriever, and ranking boundaries remain. A
small cache service is added between normalized input and query analysis.
Retrieval returns analysis metadata and timings in addition to ranked results.

## Query Normalization

One shared helper normalizes a query by trimming leading and trailing
whitespace, collapsing internal whitespace, and applying Unicode-aware
case-folding. The normalized form is used for cache identity and analytics.
The validated, trimmed original query remains the text analyzed and returned in
the `QueryAnalysis` structure.

Cache keys do not contain raw query text. They use a versioned prefix and the
SHA-256 digest of the normalized query:

```text
ai_search:query_analysis:v1:<sha256>
```

This prevents search text from appearing in Redis key listings and makes a
future schema or prompt change invalidatable by increasing the cache version.

## Deterministic and LLM Merge Policy

`QueryAnalyzer` continues to return the existing `QueryAnalysis` Pydantic
model. Its public schema remains compatible: category and brand remain scalar,
while colors and sizes remain lists.

The merge policy is field-specific:

- `price_min` and `price_max`: an explicitly detected deterministic value wins.
  The LLM value is used only when the corresponding rule value is absent.
- `colors` and `sizes`: combine rule and LLM lists, normalize values,
  deduplicate case-insensitively, and preserve deterministic values first.
- `category`: an explicit deterministic category wins. Otherwise use the LLM
  category.
- `brand`: use a deterministic brand only if a future configured extractor
  supplies one; otherwise use the LLM brand. Sprint 3.5 does not invent a brand
  dictionary or add a commerce-model field.
- `intent`, `gender`, `occasion`, `season`, `style`, and `keywords`: use valid
  LLM values, falling back to schema defaults when absent.
- `original_query`: always comes from validated application input and cannot be
  replaced by provider output.

Invalid provider data is rejected by Pydantic. If the merged output fails
validation, the analyzer returns a valid rule-only `QueryAnalysis`. A provider
exception or empty response follows the same rule-only path.

## Analyzer Lifecycle

The default `QueryAnalyzer` is created through a module-level factory decorated
with `functools.lru_cache(maxsize=1)`. This yields one analyzer and Gemini client
per Django worker process instead of one per request.

Direct `QueryAnalyzer(provider=...)` construction remains supported for unit
tests and future provider injection. The singleton factory exposes a cache
clear operation through the normal `cache_clear()` API so overridden settings
and isolated tests do not leak provider state.

The cached analyzer does not hold query-specific mutable state. Its provider
client is reused only for stateless structured-analysis calls.

## Query Analysis Cache

A focused cache service owns serialization, lookup, and storage of
`QueryAnalysis` values. It uses Django's configured default cache and validates
cached data through Pydantic before returning it.

The analysis workflow is:

1. Normalize the query and build its hashed cache key.
2. Read the cache.
3. If a valid cached object exists, return it with `cache_hit=True`.
4. On a miss, analyze with the reusable analyzer.
5. Store the validated semantic fields for the configured TTL, excluding
   `original_query`.
6. Reconstruct `QueryAnalysis` with the current trimmed request query and
   return it with `cache_hit=False`.

A cache hit also reconstructs `original_query` from the current request. Thus
queries that normalize to the same key can share semantic analysis without a
response incorrectly echoing the capitalization or spacing of an earlier
request.

Malformed cached data is discarded and recomputed. Cache read/write exceptions
are logged without query text and degrade to uncached analysis. A cache outage
must never prevent product retrieval.

Configuration uses:

```text
AI_SEARCH_QUERY_CACHE_TTL=900
REDIS_URL=redis://...
```

When `REDIS_URL` is absent, Django uses `LocMemCache`. When present, Django uses
its built-in `django.core.cache.backends.redis.RedisCache`; the `redis` Python
package is added as the only new runtime dependency. Tests use an isolated
local-memory cache.

## PostgreSQL JSON Metadata Filtering

Filtering continues to receive a `ProductSearchDocument` queryset and a
validated `QueryAnalysis`. It returns a lazily filtered queryset so keyword and
semantic retrievers can compose their PostgreSQL queries normally.

Rules are:

- price uses numeric `metadata__price__gte` and `metadata__price__lte` lookups;
- category, brand, and gender use exact case-insensitive JSON scalar lookups;
- each requested color uses JSON containment equivalent to
  `metadata @> {"colors": ["black"]}`;
- each requested size uses JSON containment equivalent to
  `metadata @> {"sizes": ["XL"]}`;
- multiple colors are ORed with one another;
- multiple sizes are ORed with one another;
- separate attribute groups are ANDed.

Filter values are normalized consistently before query construction. There is
no substring match, so `black` does not match `blackberry`.

The product-document generator keeps human-readable colors and sizes in search
text, but stores canonical filter values in metadata: colors use Unicode
case-folding and sizes use uppercase. Category, brand, and gender can retain
their display values because their scalar lookups are case-insensitive. Existing
documents must be rebuilt once after deployment to canonicalize array metadata;
unchanged embedding text retains its existing semantic hash, so current vectors
remain usable and do not need regeneration.

Exact JSON containment is PostgreSQL-specific. Unit tests that inspect merge,
cache, timing, and API behavior remain database-independent where practical;
containment and retriever integration tests run against an isolated PostgreSQL
test database with pgvector enabled. Tests must never use the deployed database.

## Retrieval Timing and Result Contract

`retrieve_products()` retains its current input and ranked-result behavior. Its
dictionary response is extended with:

```python
{
    "analysis": {...},
    "results": [...],
    "cache_hit": False,
    "timings": {
        "analysis_ms": 0.0,
        "filter_ms": 0.0,
        "keyword_ms": 0.0,
        "semantic_ms": 0.0,
        "ranking_ms": 0.0,
        "total_ms": 0.0,
    },
}
```

Durations use `time.perf_counter()` and are rounded only at the service
boundary. `filter_ms` measures construction of metadata predicates; the
database execution caused by those predicates is naturally included in each
retriever's measured query time. The service does not materialize a separate
filtered ID list because that would add a database round trip and could make
performance worse.

Semantic timing is recorded even when vector retrieval fails. A semantic
failure produces keyword-only results and a safe warning. Ranking timing covers
score normalization, candidate merge, scoring, sorting, and output truncation.
The service's `total_ms` covers query analysis through ranked retrieval.

The view measures the complete request work after validation and replaces
`total_ms` with the end-to-end duration used for persisted analytics. Timing
and cache-state data stay internal to retrieval and analytics; the public API
continues to return only analysis and product results. Timings contain no
prompts, exception messages, keys, account identifiers, or provider payloads.

## Search Query Analytics

`SearchQueryLog` becomes an anonymous operational record with these fields:

- `query`: the validated and trimmed search query, maximum 500 characters;
- `normalized_query`: its normalized form, maximum 500 characters and indexed;
- `analysis`: the validated structured analysis JSON;
- `result_count`: the number of serialized products returned;
- `execution_time_ms`: total end-to-end search duration;
- `cache_hit`: whether query analysis came from cache;
- `timings`: the required phase timing dictionary;
- `created_at`: creation timestamp.

The existing fields are migrated with `RenameField` operations:

- `original_query` becomes `query`;
- `extracted_filters` becomes `analysis`.

This preserves existing values. New non-null fields receive safe defaults for
existing rows. The existing `user` foreign key is removed so search telemetry
does not retain account identity. Existing search-log user associations are
discarded, but product, search-document, embedding, query, analysis, result
count, and timestamp data are untouched.

Every valid completed search is logged, including zero-result searches. A
failure to write analytics is logged safely and does not change an otherwise
successful API response.

The admin gains read-oriented list columns and filters for result count,
cache-hit state, execution time, and creation time. It does not expose secrets
or provider responses.

## API Failure Handling

Request validation remains at the view boundary:

- malformed JSON, non-object bodies, empty/non-string queries, and invalid
  limits return HTTP 400;
- Gemini unavailability yields rule-only analysis;
- cache unavailability yields uncached analysis;
- vector/provider unavailability yields keyword-only results;
- query-log write failure still returns the successful search response;
- an unrecoverable retrieval or database failure returns a generic HTTP 500
  response without internal details.

Exceptions are logged with operation context but without raw request bodies,
credentials, provider payloads, or user/account identifiers. Search query text
is persisted only in the explicit analytics columns required by this sprint;
it is not duplicated into exception logs.

## Database Migration Safety

One new `ai_search` migration follows `0004_sprint3_query_log` and performs:

1. rename `original_query` to `query`;
2. rename `extracted_filters` to `analysis`;
3. add `normalized_query` with a temporary/default empty value and an index;
4. add `execution_time_ms` with zero default;
5. add `cache_hit` with false default;
6. add `timings` with an empty-dictionary default;
7. populate `normalized_query` for existing rows with a data migration;
8. remove the `user` foreign key.

No product, search-document, or embedding table is altered. Existing search
queries and analyses remain usable. The only intentionally removed data is the
account association on historical query logs, as approved for privacy.

Before production migration, take a PostgreSQL backup. The operations affect
only the small analytics table and do not require regenerating documents or
embeddings.

## Files Changed

Expected production changes:

```text
ai_search/
|-- admin.py
|-- models.py
|-- views.py
|-- filters/metadata.py
|-- query_understanding/analyzer.py
|-- query_understanding/cache.py          # new
|-- query_understanding/normalization.py  # new shared helper
|-- services/product_document_service.py
|-- services/retrieval_service.py
`-- migrations/0005_*.py                  # new

Ecommerce_Storefront/settings.py
Ecommerce_Storefront/test_settings.py
.env.example
requirements.txt
```

Expected test changes:

```text
ai_search/tests/test_query_understanding.py
ai_search/tests/test_filters.py
ai_search/tests/test_ranking.py
ai_search/tests/test_api.py
ai_search/tests/test_query_cache.py        # new
ai_search/tests/test_query_logging.py      # new or folded into API tests
```

Documentation is added under `docs/superpowers/specs/` and, during
implementation, an `ai_search/README.md` records configuration, deployment,
cache behavior, migrations, and test commands.

## Testing Strategy

Development follows test-driven implementation. Tests cover:

- deterministic price/category precedence over conflicting LLM output;
- union and deduplication of rule and LLM colors and sizes;
- empty, missing, invalid, and exception-producing provider output;
- reuse of the default analyzer/provider instance;
- cache miss followed by cache hit without a second analyzer call;
- cache-key normalization and hashing;
- malformed cache data and cache backend failure;
- exact JSON array containment, including `black` not matching `blackberry`;
- exact category and brand filtering;
- minimum, maximum, and ranged price filtering;
- multiple filters and OR-within/AND-between semantics;
- timing keys and non-negative numeric values;
- semantic failure returning keyword-only results;
- analysis failure returning rule-based results;
- successful and zero-result analytics rows;
- query-log failure not breaking a successful response;
- malformed requests and generic unexpected-error responses;
- migration consistency and Django system checks.

The current SQLite test-startup failure is treated as a test-infrastructure
issue, not hidden. PostgreSQL/pgvector integration tests use a dedicated test
database. Fast unit tests may use SQLite only when they do not initialize or
exercise PostgreSQL-specific model/index behavior.

No test calls Gemini or Redis over the network. Provider and external-cache
boundaries are mocked or use Django's local-memory backend.

## Deployment

1. Add `REDIS_URL` to production when a Redis service is available. If it is
   omitted, the application remains functional with process-local memory cache.
2. Set `AI_SEARCH_QUERY_CACHE_TTL`, or accept the 900-second default.
3. Install the new `redis` dependency.
4. Back up PostgreSQL.
5. Run `python manage.py migrate ai_search`.
6. Run `python manage.py build_search_documents` once to canonicalize existing
   color and size metadata. Existing vectors remain usable when semantic text
   has not changed.
7. Run `python manage.py check`.
8. Execute the isolated PostgreSQL test suite before release.
9. Search for representative exact, semantic, conflict, repeated, and
   zero-result queries.
10. Confirm cache hits, timing values, and zero-result rows in admin.

An embedding rebuild is not required for this migration.

## Completion Criteria

Sprint 3.5 is complete when:

- deterministic evidence cannot be erased by empty or conflicting LLM output;
- exact JSON filtering prevents substring false positives;
- one analyzer/provider instance is reused per Django worker;
- repeated normalized queries reuse validated cached analysis;
- Redis is environment-configurable and local development requires no Redis;
- anonymous query logs capture analysis, no-result searches, cache state, and
  required timings without account identity;
- cache, Gemini, semantic retrieval, and logging failures degrade safely;
- API errors never disclose internal exception details;
- migrations preserve existing analytics except for the intentionally removed
  user relationship;
- system checks, migration checks, focused unit tests, PostgreSQL integration
  tests, and the relevant full project suite pass;
- documentation describes architecture, configuration, migration, testing, and
  deployment;
- no RAG, chatbot, recommendation, or unrelated commerce changes are present.
