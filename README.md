<div align="center">

# 🛒 Haatify — AI-Powered E-Commerce Storefront

### A Next-Generation Fashion Retail Platform with Hybrid AI Search & Smart Shopping Assistant

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-6.0-092E20?style=for-the-badge&logo=django&logoColor=white)](https://djangoproject.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Google Gemini](https://img.shields.io/badge/Google_Gemini-3.5_Flash_Lite-8E75C2?style=for-the-badge&logo=googlegemini&logoColor=white)](https://ai.google.dev/)
[![Stripe](https://img.shields.io/badge/Stripe-Checkout_&_Webhooks-635BFF?style=for-the-badge&logo=stripe&logoColor=white)](https://stripe.com)
[![Render](https://img.shields.io/badge/Deployed_on-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://haatify.onrender.com)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

<br/>

**[🌐 Live Demo](https://haatify.onrender.com)** &nbsp;·&nbsp; **[🎬 Video Demo](https://youtu.be/06E7dtBlxFk?si=zh1EPSy-Z79_eTTK)** &nbsp;·&nbsp; **[🐛 Report Bug](https://github.com/NaimurRahmannn/Hatify-An-AI-powered-online-Retailer-shop/issues)** &nbsp;·&nbsp; **[✨ Request Feature](https://github.com/NaimurRahmannn/Hatify-An-AI-powered-online-Retailer-shop/issues)**

---

</div>

## 📖 Overview

**Haatify** is an enterprise-grade, modern fashion e-commerce storefront engineered with **Django 6** and augmented with state-of-the-art **Generative AI** and **Vector Retrieval**. 

Beyond traditional online storefronts, Haatify provides:
- **Intelligent Hybrid Search (`ai_search`)**: Combines lexical full-text search (PostgreSQL trigram / BM25) with high-dimensional 768-vector embeddings (`pgvector` + Gemini Embedding 2) for deep semantic comprehension (e.g. natural language queries like *"warm winter coat for office casual"*).
- **Interactive AI Shopping Stylist (`ai_assistant`)**: An in-app conversational assistant powered by **Google Gemini 3.5 Flash Lite** that understands user preferences, recommends matching products, splits results by gender/department, and suggests one-tap conversational filter chips.
- **Full E-Commerce Life Cycle**: Cart management, dynamic variant pricing, multi-channel checkouts (Stripe Hosted Checkout with automated Webhooks, bKash, Nagad, Cash on Delivery), and dynamic PDF invoice generation.

<br/>

---

## ✨ Key Features

### 🤖 AI-Powered Capabilities
| Feature | Description |
|---|---|
| 🧠 **Semantic Vector Search** | Utilizes 768-dimensional embeddings generated with `gemini-embedding-2` stored in PostgreSQL using the `pgvector` extension with Cosine Distance indexing. |
| 🔀 **Hybrid Search Fusion** | Blends lexical keyword match scores and semantic cosine similarities for high precision & recall. |
| 💬 **AI Shopping Stylist Chatbot** | Built on **Gemini 3.5 Flash Lite** with real-time product context injection, multi-turn conversation memory, and streaming-style UX. |
| 👥 **Smart Gender/Collection Splitting** | Intelligently divides recommendations into **Men's** and **Women's** collections and prompts interactive quick-filter chips. |
| 📝 **Semantic Embedding Description** | Specialized backend metadata enrichment for fabric, fit, silhouette, color tones, and seasonal aesthetics to power precision vector matching without cluttering customer-facing product pages. |

### 🛍️ Storefront & E-Commerce Core
| Feature | Description |
|---|---|
| 👗 **Product Catalog & Variants** | Full catalog with categories (Men, Women), color/size variants, dynamic stock tracking, and variant-based pricing. |
| 🛒 **Cart & Session Management** | Session-backed shopping cart with instant quantity updates, variant switching, and stock threshold validation. |
| 💳 **Multi-Channel Checkout** | **Stripe Hosted Checkout** (Test Mode), **bKash**, **Nagad**, and **Cash on Delivery (COD)**. |
| ⚡ **Robust Webhook Handling** | Production-ready Stripe webhooks verifying signatures (`checkout.session.completed`, `charge.refunded`, async payments, etc.). |
| 🧾 **Invoice & Order Confirmation** | Instant order confirmation summaries and on-demand downloadable PDF invoices. |
| 👤 **User Authentication** | Standard registration/login, password reset flows, and single-click **Google OAuth 2.0** via `django-allauth`. |
| 🖼️ **Cloudinary Media Storage** | Scalable cloud image hosting with automatic optimizations and transformations. |
| 🛡️ **Django Admin Dashboard** | Full CRUD capabilities for products, inventory, embeddings, orders, and user permissions. |

<br/>

---

## 🛠️ Architecture & Tech Stack

```
                                  ┌────────────────────────┐
                                  │   Browser / Client     │
                                  │ (Bootstrap, JS Widget) │
                                  └───────────┬────────────┘
                                              │ HTTP / JSON API
                                              ▼
                                  ┌────────────────────────┐
                                  │   Gunicorn + Django    │
                                  │ (Ecommerce_Storefront) │
                                  └─────┬────────────┬─────┘
                                        │            │
            ┌───────────────────────────┘            └───────────────────────────┐
            ▼                                                                    ▼
┌───────────────────────┐                                            ┌───────────────────────┐
│ PostgreSQL + pgvector │                                            │   Google Gemini API   │
│ - Product Documents   │                                            │ - gemini-3.5-flash-lite│
│ - 768-dim Embeddings  │                                            │ - gemini-embedding-2  │
│ - User & Order Data   │                                            └───────────────────────┘
└───────────────────────┘                                                        ▲
            ▲                                                                    │
            └─────────────────────────── Hybrid Search ──────────────────────────┘
```

| Layer | Technologies & Tools |
|---|---|
| **Backend Framework** | Django 6.0 · Python 3.10+ · Gunicorn WSGI |
| **Generative AI / LLM** | Google Gemini 3.5 Flash Lite (`gemini-3.5-flash-lite`) |
| **Embeddings & Search** | Google Gemini Embedding 2 (`gemini-embedding-2`) · `pgvector` (HNSW / IVFFlat cosine) |
| **Database** | PostgreSQL with `pgvector` extension (via `dj-database-url`) |
| **Caching** | Redis (production) / Django LocMemCache (local fallback) |
| **Payments** | Stripe Checkout API · Webhook Signature Verification |
| **Media & Static** | Cloudinary Storage · WhiteNoise |
| **Authentication** | Django Auth · `django-allauth` · Google OAuth 2.0 PKCE |
| **Frontend UI** | HTML5 · CSS3 (Custom Glassmorphic Theme) · Bootstrap · Vanilla JS · jQuery · Font Awesome 6 |
| **Hosting & CI/CD** | Render.com (`build.sh`, `Procfile`) |

<br/>

---

## 📁 Project Structure

```text
Ecommerce-sites-with-Django/
│
├── Ecommerce_Storefront/       # Core project configuration
│   ├── settings.py             # Settings (AI Search, Gemini, Stripe, Cloudinary, DB)
│   ├── urls.py                 # Master URL routing
│   └── wsgi.py                 # WSGI application entrypoint
│
├── ai_search/                  # Hybrid & Vector Retrieval Engine
│   ├── models.py               # ProductDocument & Embedding vectors (pgvector)
│   ├── services/               # Embedding service, Hybrid retrieval & ranking
│   ├── filters/                # Metadata filtering & category extraction
│   └── management/commands/    # CLI commands (generate_embeddings, etc.)
│
├── ai_assistant/               # Conversational AI Shopping Stylist
│   ├── views.py                # Chat API endpoints (/api/ai-assistant/chat/)
│   ├── prompts.py              # System prompts, role definitions & formatting rules
│   ├── services/               # Chat service, context builder & LLM providers
│   └── serializers.py          # Chat request & response serialization
│
├── products/                   # Storefront catalog & order processing
│   ├── models.py               # Category, Product, ProductVariant, Cart, Order
│   ├── views.py                # Catalog, product detail, cart, checkout & invoice
│   └── admin.py                # Admin customization with embedding description
│
├── payments/                   # Stripe payment integration
│   ├── views.py                # Stripe checkout session creation & webhook receiver
│   ├── services.py             # Stripe API client & order reconciliation
│   └── config.py               # Stripe environment validation
│
├── accounts/                   # Authentication & User Management
│   ├── models.py               # Profile model & token verification
│   └── views.py                # Login, registration, profile & OAuth callbacks
│
├── home/                       # Landing page & contact views
├── base/                       # Shared base models, mixins & email utilities
│
├── templates/                  # Django HTML templates
│   ├── base/                   # Base layout, navbar, footer & AI assistant modal
│   ├── home/                   # Hero section & featured products
│   ├── product/                # Product details, cart, checkout & invoices
│   ├── payments/               # Payment success & cancellation pages
│   └── accounts/               # Login, registration & account dashboards
│
├── public/static/              # Static assets
│   ├── css/                    # Custom stylesheets (ui.css, ai_assistant.css)
│   ├── js/                     # Client logic (ai_assistant.js, script.js)
│   └── images/                 # Brand assets and placeholders
│
├── Procfile                    # Render production process definition (timeout 120s)
├── build.sh                    # Automated Render build script
├── requirements.txt            # Python dependencies
└── manage.py                   # Django CLI tool
```

<br/>

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **PostgreSQL** with `pgvector` enabled (or Docker PostgreSQL image with pgvector)
- **Google Gemini API Key** ([Google AI Studio](https://aistudio.google.com/))
- **Cloudinary Account** (for media hosting)
- **Stripe Account** (for test mode payments)

---

### Step-by-Step Installation

#### 1. Clone the Repository
```bash
git clone https://github.com/NaimurRahmannn/Hatify-An-AI-powered-online-Retailer-shop.git
cd Hatify-An-AI-powered-online-Retailer-shop
```

#### 2. Set Up Virtual Environment
```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

#### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 4. Configure Environment Variables
Create a `.env` file in the project root based on `.env.example`:
```bash
cp .env.example .env
```
Fill in your API credentials:
```env
SECRET_KEY=your-django-secret-key
DATABASE_URL=postgresql://postgres:password@localhost:5432/haatify_db
DJANGO_DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

# Google Gemini API
GEMINI_API_KEY=AIzaSy...
AI_SEARCH_EMBEDDING_PROVIDER=gemini
AI_SEARCH_EMBEDDING_MODEL=gemini-embedding-2
AI_CHAT_MODEL=gemini-3.5-flash-lite

# Cloudinary
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# Stripe Test Mode
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_CURRENCY=usd
STRIPE_BDT_PER_USD=120.50

# Google OAuth (Optional)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

#### 5. Run Database Migrations
```bash
python manage.py migrate
```

#### 6. Generate Vector Embeddings for Products
Generate 768-dimensional embeddings for all existing products in your database:
```bash
python manage.py generate_embeddings --batch-size 10
```

#### 7. Create Superuser & Run Development Server
```bash
python manage.py createsuperuser
python manage.py runserver
```

Open **http://127.0.0.1:8000** in your browser! 🎉

<br/>

---

## 🧠 AI Search & Assistant Management

### Management Commands
| Command | Description |
|---|---|
| `python manage.py generate_embeddings` | Generates semantic vector embeddings for all products missing embeddings. |
| `python manage.py generate_embeddings --force` | Re-computes and updates embeddings for all products. |
| `python manage.py test ai_search` | Runs comprehensive test suite for hybrid retrieval and filtering. |
| `python manage.py test ai_assistant` | Runs unit tests for context building, chat sessions, and serializers. |

---

## 💳 Stripe Test Payments & Webhooks

### 1. Test Cards

| Scenario | Card Number | Expiry | CVC |
|---|---|---|---|
| **Successful Payment** | `4242 4242 4242 4242` | Any future date | Any 3 digits |
| **3D Secure (Auth)** | `4000 0025 0000 3155` | Any future date | Any 3 digits |
| **Declined Payment** | `4000 0000 0000 0002` | Any future date | Any 3 digits |

### 2. Local Webhook Forwarding (Stripe CLI)
```bash
stripe listen --forward-to localhost:8000/payments/webhook/ --events checkout.session.completed,checkout.session.async_payment_succeeded,checkout.session.async_payment_failed,checkout.session.expired,payment_intent.payment_failed,charge.refunded
```
Copy the printed `whsec_...` secret to your `.env` as `STRIPE_WEBHOOK_SECRET`.

<br/>

---

## 🌍 Production Deployment (Render)

This repository is configured for one-click deployment on **Render.com**:

1. **Connect GitHub Repo**: Link your repository to a new Render Web Service.
2. **Build Command**:
   ```bash
   ./build.sh
   ```
3. **Start Command**:
   ```bash
   gunicorn Ecommerce_Storefront.wsgi --timeout 120 --workers 2
   ```
   *(Note: `--timeout 120` ensures multi-step GenAI API requests complete reliably).*
4. **Environment Variables**: Add all variables from your `.env` into Render's Environment settings.
5. **Database**: Attach a Render PostgreSQL instance (enable `pgvector` by running `CREATE EXTENSION IF NOT EXISTS vector;`).

<br/>

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<br/>

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.
