# Haatify

Haatify is a Django fashion-commerce application with a PostgreSQL hybrid
retrieval engine and an in-store AI shopping assistant. It combines a complete
storefront and checkout flow with keyword search, vector search, structured
query understanding, and retrieval-augmented Gemini responses.

[Live application](https://haatify.onrender.com) | [Repository](https://github.com/NaimurRahmannn/Ecommerce-sites-with-Django) | [Issues](https://github.com/NaimurRahmannn/Ecommerce-sites-with-Django/issues)

## Contents

- [What is implemented](#what-is-implemented)
- [Known scope and limitations](#known-scope-and-limitations)
- [Architecture](#architecture)
- [Technology stack](#technology-stack)
- [Project structure](#project-structure)
- [Local setup](#local-setup)
- [Environment variables](#environment-variables)
- [Preparing AI search data](#preparing-ai-search-data)
- [API reference](#api-reference)
- [Payments and Stripe webhooks](#payments-and-stripe-webhooks)
- [Testing](#testing)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Security notes](#security-notes)
- [Roadmap](#roadmap)
- [License](#license)

## What is implemented

### Storefront and commerce

- Men's and women's category browsing
- Product detail pages with image galleries
- Color and size variants
- Session-backed cart operations
- Buy-now and standard checkout paths
- Persisted orders and immutable order-item snapshots
- Manual bKash, Nagad, and cash-on-delivery payment choices
- Stripe-hosted Checkout with retry, success, and cancellation flows
- Order invoice pages
- Django admin management for catalog, orders, AI documents, and embeddings

### Accounts

- Email/password registration and login
- Email verification through SMTP
- Optional Google OAuth through `django-allauth`
- User-owned order and payment pages

### Hybrid product search

The `ai_search` application provides:

- Automatic `ProductSearchDocument` synchronization through Django signals
- AI-oriented searchable text and JSON metadata per product
- PostgreSQL full-text search using `SearchVector`, `SearchQuery`, and
  `SearchRank`
- A functional GIN index configured with PostgreSQL's `simple` text-search
  configuration
- 768-dimensional product embeddings stored with `pgvector`
- Cosine-distance semantic retrieval through an HNSW index
- Weighted fusion of normalized keyword and semantic scores
- Rule-based extraction for explicit colors, sizes, categories, and prices
- Optional Gemini structured query analysis
- Exact metadata filtering for price, category, brand, color, size, and gender
- Cached query analysis through Django's cache framework
- Anonymous search analytics, cache-hit tracking, no-result tracking, and
  per-stage performance timings
- Keyword-only degradation when query embedding or vector retrieval fails

### AI shopping assistant

The `ai_assistant` application adds a browser chat widget and a JSON API that:

- Classifies product-search, comparison, recommendation, and general intents
- Uses recent conversation messages to make retrieval context-aware
- Retrieves up to six products through the hybrid search service
- Builds bounded product context for Gemini
- Returns product cards with stable product links and images
- Persists user and assistant messages for authenticated and anonymous sessions
- Prevents users or anonymous sessions from reading another conversation
- Applies cache-backed per-caller rate limiting
- Records retrieval, context-building, model, and total response timings
- Falls back to retrieved product links if LLM generation is unavailable

## Known scope and limitations

- Personalized recommendations are not implemented yet.
  `RecommendationService` is an explicit placeholder and recommendation intent
  currently falls back to hybrid product retrieval.
- The product model has no stock-quantity or inventory field. Any future
  availability metadata remains empty until inventory is added to the commerce
  domain.
- The AI model names are configuration values. Use model identifiers available
  to your own Gemini account rather than assuming the repository defaults are
  enabled for every account.

## Architecture

### Application overview

```mermaid
flowchart TB
    Browser["Browser / Client"]

    subgraph Django["Django application"]
        Storefront["Storefront<br/>products, accounts, payments"]
        SearchAPI["Hybrid Search API<br/>POST /api/ai-search/"]
        AssistantAPI["AI Assistant API<br/>POST /api/ai-assistant/chat/"]
        Intent["Intent router and conversation memory"]
        Retrieval["Hybrid retrieval and ranking"]
        Context["Bounded product context builder"]
    end

    subgraph Data["PostgreSQL"]
        Commerce[("Catalog, users, orders")]
        Documents[("Product search documents<br/>and JSON metadata")]
        Vectors[("768-dimensional pgvector<br/>embeddings")]
        Conversations[("Conversations, messages,<br/>and telemetry")]
    end

    subgraph External["External services"]
        Gemini["Google Gemini<br/>query analysis, embeddings, chat"]
        Redis["Redis<br/>shared cache and rate limits"]
        Stripe["Stripe Checkout<br/>and signed webhooks"]
        Cloudinary["Cloudinary media storage"]
    end

    Browser --> Storefront
    Browser --> SearchAPI
    Browser --> AssistantAPI

    Storefront --> Commerce
    Storefront --> Stripe
    Storefront --> Cloudinary

    SearchAPI --> Retrieval
    AssistantAPI --> Intent
    Intent --> Retrieval
    Intent --> Conversations
    Retrieval --> Documents
    Retrieval --> Vectors
    Retrieval --> Context
    Context --> Gemini

    SearchAPI -.->|cached analysis| Redis
    AssistantAPI -.->|rate limits| Redis
    Retrieval -.->|query vectors and structured analysis| Gemini
```

### Hybrid retrieval flow

```mermaid
flowchart TD
    Query["User query"] --> Normalize["Normalize query"]
    Normalize --> Cache{"Cached structured analysis?"}
    Cache -- Yes --> Analysis["Validated QueryAnalysis"]
    Cache -- No --> Rules["Deterministic rule extraction"]
    Cache -- No --> LLM["Optional Gemini structured analysis"]
    Rules --> Merge["Confidence-aware merge<br/>explicit rules take priority"]
    LLM --> Merge
    Merge --> Analysis
    Analysis --> Filters["Exact PostgreSQL JSON metadata filters"]

    Filters --> Keyword["Keyword retrieval<br/>PostgreSQL full-text search"]
    Filters --> Semantic["Semantic retrieval<br/>pgvector cosine distance"]

    Keyword --> Fusion["Normalize scores and apply configured weights"]
    Semantic --> Fusion
    Semantic -.->|provider/vector failure| KeywordOnly["Keyword-only fallback"]
    KeywordOnly --> Fusion
    Fusion --> Ranking["Deterministic final ranking"]
    Ranking --> Results["Ranked products"]
```

Deterministic evidence has priority for explicit values such as price limits.
Rule and LLM color/size values are merged so an empty or conflicting model
response cannot erase information directly present in the query.

### Product document lifecycle

```text
Product or variant change
   |
   v
Django signal
   |
   v
ProductSearchDocument update
   |
   v
Embedding marked pending only when semantic content changed
   |
   v
generate_embeddings command
   |
   v
Gemini vector -> ProductEmbedding
```

Signals do not call Gemini. Product writes therefore remain independent from
provider availability and rate limits.

## Technology stack

| Area | Technology |
|---|---|
| Web framework | Django 5.2 |
| Runtime | Python 3.10+ |
| Production server | Gunicorn |
| Database | PostgreSQL |
| Vector storage | pgvector |
| Query validation | Pydantic 2 |
| AI SDK | Google Gen AI SDK |
| Cache | Redis in production; `LocMemCache` fallback |
| Payments | Stripe-hosted Checkout and signed webhooks |
| Authentication | Django auth and django-allauth |
| Media | Cloudinary |
| Static files | WhiteNoise |
| Frontend | Django templates, Bootstrap, vanilla JavaScript, jQuery |
| Deployment | Render-compatible `build.sh` and `Procfile` |

The exact Python package versions are defined in
[`requirements.txt`](requirements.txt).

## Project structure

```text
.
|-- Ecommerce_Storefront/       Django settings, root URLs, WSGI, test settings
|-- accounts/                   Registration, login, verification, Google OAuth
|-- ai_assistant/               RAG chat API, memory, intent routing, evaluation
|   |-- services/               Chat orchestration, context, LLM, memory
|   `-- evaluation/             Retrieval evaluation dataset and evaluator
|-- ai_search/                  AI document and hybrid retrieval foundation
|   |-- filters/                Structured JSON metadata filtering
|   |-- management/commands/    Document and embedding rebuild commands
|   |-- query_understanding/    Rules, Gemini analyzer, schemas, query cache
|   |-- retrievers/             PostgreSQL keyword and pgvector retrieval
|   |-- services/               Document, embedding, and ranking workflows
|   `-- tests/                  Search unit and PostgreSQL integration tests
|-- base/                       Shared base model and email utilities
|-- home/                       Home and contact pages
|-- payments/                   Stripe sessions, order service, signed webhooks
|-- products/                   Catalog, variants, cart, checkout, orders
|-- public/static/              CSS, JavaScript, images, and chat widget client
|-- templates/                  Server-rendered storefront templates
|-- tests/                      Project-level source and configuration tests
|-- build.sh                    Render build command
|-- Procfile                    Gunicorn process definition
|-- manage.py                   Django command entry point
`-- requirements.txt            Python dependencies
```

## Local setup

### Prerequisites

- Python 3.10 or newer
- PostgreSQL with the `pgvector` extension available
- A PostgreSQL role allowed to create the `vector` extension, or an
  administrator who can enable it before migrations
- Node.js only if you want to run the standalone chat-widget tests
- A Gemini API key to generate embeddings or LLM responses
- Cloudinary credentials to upload product images
- Stripe test credentials to exercise hosted checkout

### 1. Clone the repository

```bash
git clone https://github.com/NaimurRahmannn/Ecommerce-sites-with-Django.git
cd Ecommerce-sites-with-Django
```

### 2. Create a virtual environment

Linux or macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure the environment

Copy `.env.example` to `.env` and supply your own values.

Linux or macOS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Never commit `.env` or paste real credentials into issues, logs, source files,
documentation, or test fixtures.

### 5. Create the database and run migrations

Create a PostgreSQL database, set `DATABASE_URL`, then run:

```bash
python manage.py migrate
```

The initial `ai_search` migration runs `CREATE EXTENSION vector`. If the
application role cannot create extensions, a database administrator must run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Then rerun migrations.

### 6. Create an administrator

```bash
python manage.py createsuperuser
```

### 7. Start Django

```bash
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. The admin is available at
<http://127.0.0.1:8000/admin/>.

## Environment variables

### Core Django and database

| Variable | Required | Purpose |
|---|---:|---|
| `SECRET_KEY` | Yes | Django cryptographic secret |
| `DATABASE_URL` | Yes | PostgreSQL connection URL |
| `DJANGO_DEBUG` | No | Enables debug mode when set to `True`; default is `False` |
| `ALLOWED_HOSTS` | Production | Comma-separated host names |

Example:

```env
SECRET_KEY=replace-with-a-long-random-value
DATABASE_URL=postgresql://postgres:password@127.0.0.1:5432/haatify
DJANGO_DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
```

### AI search and assistant

| Variable | Required | Default / purpose |
|---|---:|---|
| `GEMINI_API_KEY` | For Gemini | Shared Gemini credential for embeddings, query analysis, and chat |
| `AI_SEARCH_EMBEDDING_PROVIDER` | No | `gemini` |
| `AI_SEARCH_EMBEDDING_MODEL` | No | Embedding model identifier |
| `GEMINI_EMBEDDING_MODEL` | No | Backward-compatible embedding-model fallback |
| `AI_QUERY_PROVIDER` | No | `gemini` |
| `AI_QUERY_MODEL` | No | Structured query-analysis model identifier |
| `AI_CHAT_PROVIDER` | No | `gemini` |
| `AI_CHAT_MODEL` | No | Assistant response model identifier |
| `AI_SEARCH_QUERY_CACHE_TTL` | No | Analysis-cache lifetime in seconds; default `900` |
| `REDIS_URL` | Production | Redis URL; without it Django uses process-local memory |
| `AI_SEARCH_TEST_DATABASE_URL` | Tests | Dedicated disposable PostgreSQL test database |

The embedding column has a fixed dimension of 768. Changing dimensions is a
schema migration and requires regenerating every embedding.

### Cloudinary

| Variable | Required | Purpose |
|---|---:|---|
| `CLOUDINARY_CLOUD_NAME` | For uploads | Cloudinary cloud name |
| `CLOUDINARY_API_KEY` | For uploads | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | For uploads | Cloudinary API secret |

### Email and authentication

| Variable | Required | Purpose |
|---|---:|---|
| `EMAIL_HOST_USER` | For verification email | Gmail/SMTP account |
| `EMAIL_HOST_PASSWORD` | For verification email | SMTP app password |
| `DEFAULT_FROM_EMAIL` | No | Sender address; defaults to `EMAIL_HOST_USER` |
| `GOOGLE_CLIENT_ID` | For Google OAuth | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | For Google OAuth | Google OAuth client secret |

Google login is displayed only when both Google credentials are configured.

### Stripe test mode

| Variable | Required | Purpose |
|---|---:|---|
| `STRIPE_PUBLIC_KEY` | For Stripe | Must be a `pk_test_...` key |
| `STRIPE_SECRET_KEY` | For Stripe | Must be an `sk_test_...` key |
| `STRIPE_WEBHOOK_SECRET` | For Stripe | Must be a `whsec_...` signing secret |
| `STRIPE_CURRENCY` | For Stripe | Current integration expects `usd` |
| `STRIPE_BDT_PER_USD` | For Stripe | Positive BDT conversion rate per USD |

Stripe Checkout is enabled only when all test-mode values are valid. Live
Stripe keys are intentionally rejected by the current configuration.

### Optional deployment bootstrap

| Variable | Purpose |
|---|---|
| `DJANGO_CREATE_SUPERUSER` | Set to `1` to let `build.sh` create a superuser |
| `DJANGO_SUPERUSER_USERNAME` | Bootstrap superuser name |
| `DJANGO_SUPERUSER_EMAIL` | Bootstrap superuser email |
| `DJANGO_SUPERUSER_PASSWORD` | Bootstrap superuser password |

## Preparing AI search data

Migrations create the search tables and indexes, but existing products still
need documents and embeddings.

### Build or rebuild product documents

```bash
python manage.py build_search_documents
```

This command is safe to rerun. It updates one search document per product and
marks embeddings pending only when semantic content has changed.

### Generate missing or stale embeddings

```bash
python manage.py generate_embeddings
```

The command skips embeddings that already match the current product content and
configured model. It processes documents sequentially and continues after an
individual provider failure.

Force regeneration after deliberately changing the embedding model or semantic
strategy:

```bash
python manage.py generate_embeddings --force
```

Embedding generation is not run automatically by `build.sh`; run it as a
separate deployment or maintenance operation.

## API reference

Both APIs accept JSON through `POST` and remain protected by Django's CSRF
middleware. Same-origin browser clients should send the `X-CSRFToken` header.

### Hybrid product search

Endpoint:

```text
POST /api/ai-search/
```

Request:

```json
{
  "query": "black hoodie under 3000",
  "limit": 10
}
```

`query` is required and limited to 500 characters. `limit` is optional and must
be between 1 and 50.

Example response:

```json
{
  "analysis": {
    "original_query": "black hoodie under 3000",
    "intent": "product_search",
    "category": "hoodie",
    "colors": ["black"],
    "sizes": [],
    "price_max": 3000.0,
    "keywords": []
  },
  "results": [
    {
      "id": "product-uuid",
      "name": "Black Hoodie",
      "price": "2500.00",
      "keyword_score": 1.0,
      "semantic_score": 0.91,
      "final_score": 0.955
    }
  ]
}
```

Valid searches with no matches return HTTP 200 and an empty `results` list.
Gemini/vector failure degrades to deterministic analysis and keyword results
where possible.

### AI shopping assistant

Endpoint:

```text
POST /api/ai-assistant/chat/
```

New conversation request:

```json
{
  "message": "Show me a black winter jacket under 5000"
}
```

Continue an owned conversation by sending the returned UUID:

```json
{
  "message": "Do you have it in XL?",
  "conversation_id": "00000000-0000-0000-0000-000000000000"
}
```

Example response:

```json
{
  "conversation_id": "00000000-0000-0000-0000-000000000000",
  "answer": "Here are the closest matching jackets.",
  "products": [
    {
      "id": "product-uuid",
      "name": "Black Winter Jacket",
      "price": 4500.0,
      "image": "https://example.com/image.jpg",
      "category": "Jackets",
      "url": "/product/black-winter-jacket/",
      "metadata": {}
    }
  ],
  "metadata": {
    "intent": "product_search",
    "timings": {}
  }
}
```

The API returns:

- HTTP 400 for malformed or invalid input
- HTTP 404 when the caller does not own the requested conversation
- HTTP 429 when the per-minute cache-backed rate limit is exceeded
- HTTP 500 with a generic message for an unexpected processing failure

Default limits in the current view are 10 requests per minute for anonymous
clients and 50 for authenticated users.

## Payments and Stripe webhooks

Haatify creates order and line-item records from server-side product prices
before requesting a Stripe Checkout Session. Client-submitted prices are not
trusted.

Local Stripe webhook forwarding:

```bash
stripe listen \
  --forward-to localhost:8000/payments/webhook/ \
  --events checkout.session.completed,checkout.session.async_payment_succeeded,checkout.session.async_payment_failed,checkout.session.expired,payment_intent.payment_failed,charge.refunded
```

Copy the generated `whsec_...` value to `STRIPE_WEBHOOK_SECRET`.

The webhook handler:

- verifies Stripe signatures;
- verifies paid amount and currency against the stored order;
- treats duplicate event IDs idempotently;
- handles asynchronous success, failure, expiry, payment-intent failure, and
  full refunds;
- does not let late failure events downgrade paid or refunded orders.

Useful Stripe test cards are documented in Stripe's official testing guide.

## Testing

Automated tests mock external Gemini and Stripe boundaries. They must not use
production credentials or the deployed database.

### Fast AI-search suite

```bash
python manage.py test ai_search \
  --settings=Ecommerce_Storefront.test_settings
```

Without `AI_SEARCH_TEST_DATABASE_URL`, this uses an in-memory SQLite database.
PostgreSQL full-text, JSONB containment, pgvector, GIN, and HNSW integration
tests are skipped in that mode.

### PostgreSQL/pgvector AI-search suite

Set `AI_SEARCH_TEST_DATABASE_URL` to a dedicated disposable test database, not
`DATABASE_URL`, then run the same command.

Linux or macOS:

```bash
export AI_SEARCH_TEST_DATABASE_URL=postgresql://postgres:password@127.0.0.1:5432/haatify_test
python manage.py test ai_search --settings=Ecommerce_Storefront.test_settings
```

Windows PowerShell:

```powershell
$env:AI_SEARCH_TEST_DATABASE_URL = "postgresql://postgres:password@127.0.0.1:5432/haatify_test"
python manage.py test ai_search --settings=Ecommerce_Storefront.test_settings
```

### Assistant and frontend tests

```bash
python manage.py test ai_assistant \
  --settings=Ecommerce_Storefront.test_settings

node ai_assistant/tests_frontend.js
```

### Payments, accounts, and complete Django suite

```bash
python manage.py test payments.tests accounts products tests \
  --settings=Ecommerce_Storefront.test_settings

python manage.py test \
  --settings=Ecommerce_Storefront.test_settings
```

### Configuration checks

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
```

## Deployment

The repository includes Render-compatible deployment files.

`build.sh` performs:

1. `pip install -r requirements.txt`
2. `python manage.py collectstatic --noinput`
3. `python manage.py migrate`
4. optional superuser creation when `DJANGO_CREATE_SUPERUSER=1`

The `Procfile` starts:

```text
gunicorn Ecommerce_Storefront.wsgi --timeout 120 --workers 2
```

For a production deployment:

1. Provision PostgreSQL with pgvector support.
2. Provision Redis and set `REDIS_URL` if multiple workers must share query
   cache and rate-limit counters.
3. Add all required secrets through the host's environment-variable manager.
4. Use `./build.sh` as the build command.
5. Use the checked-in `Procfile` as the web process.
6. Run `build_search_documents` after loading or migrating catalog data.
7. Run `generate_embeddings` as a separate maintenance job.
8. Register the production Stripe webhook endpoint:
   `https://your-host/payments/webhook/`.
9. Configure Google OAuth redirect URLs and Cloudinary credentials if those
   integrations are enabled.

## Troubleshooting

### `vector` extension migration fails

Ensure PostgreSQL has pgvector installed and that the migration role may create
extensions. Otherwise ask an administrator to run
`CREATE EXTENSION IF NOT EXISTS vector;`.

### Search returns no semantic matches

Run:

```bash
python manage.py build_search_documents
python manage.py generate_embeddings
```

Then inspect `ProductEmbedding.status`, `error_message`, model name, and content
hash in Django admin. Keyword search can continue working while embeddings are
missing or failed.

### Gemini calls fail

Verify `GEMINI_API_KEY` and the configured model identifiers. Structured query
analysis falls back to deterministic rules, vector search falls back to keyword
retrieval, and the assistant can fall back to retrieved product links.

### Redis is unavailable

Remove `REDIS_URL` locally to use `LocMemCache`. LocMem is process-local, so it
does not provide shared cache or shared rate-limit counters across multiple
Gunicorn workers.

### Stripe is not shown at checkout

Confirm that all Stripe values use test-mode prefixes, currency is `usd`, and
`STRIPE_BDT_PER_USD` is a positive decimal. The integration deliberately stays
disabled for incomplete or live-key configurations.

### Google sign-in is hidden

Both `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are required. Restart Django
after changing them.

## Security notes

- Keep `.env` out of version control and rotate any exposed credential.
- Search and assistant APIs retain Django CSRF protection.
- Assistant conversations are scoped to the authenticated user or anonymous
  session to prevent cross-conversation access.
- Anonymous chat rate limiting uses the request IP and fails open if the cache
  is unavailable.
- Stripe webhook payloads are accepted only after signature verification.
- Stripe amounts are checked against server-persisted order totals.
- Webhook event IDs are unique, making repeated Stripe deliveries harmless.
- API error responses avoid returning provider, database, or exception details.
- Search analytics are anonymous; assistant conversations may be associated
  with the signed-in user and should be retained according to your privacy
  policy.

## Roadmap

- Personalized recommendation engine using preferences and purchase history
- Conversation summarization for longer sessions
- Structured inventory and stock-availability integration
- Background embedding jobs with retry scheduling
- Expanded retrieval evaluation and quality monitoring

## Contributing

1. Fork the repository.
2. Create a focused feature branch.
3. Add or update tests for behavior changes.
4. Run the relevant Django and frontend suites.
5. Open a pull request describing the change, migration impact, and test
   evidence.

Please never include credentials, customer data, production database dumps, or
real payment details in a contribution.

## License

Haatify is available under the [MIT License](LICENSE).
