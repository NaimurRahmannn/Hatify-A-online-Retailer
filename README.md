<div align="center">

# ðŸ›’ Haatify â€” E-Commerce Storefront

### A modern, full-featured e-commerce platform built with Django

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-5.2-092E20?style=for-the-badge&logo=django&logoColor=white)](https://djangoproject.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Render](https://img.shields.io/badge/Deployed_on-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://haatify.onrender.com)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

<br/>

**[ðŸŒ Live Demo](https://haatify.onrender.com)** &nbsp;Â·&nbsp; **[ðŸ› Report Bug](../../issues)** &nbsp;Â·&nbsp; **[âœ¨ Request Feature](../../issues)**

---

</div>

## ðŸ“– About

**Haatify** is a clean, responsive e-commerce storefront designed for fashion retail. It supports product browsing by categories (Men & Women), shopping cart management, order checkout with multiple payment options, user authentication, and an admin dashboard for managing inventory.

<br/>

## ðŸŽ¬ Project Video

- YouTube Demo: https://youtu.be/06E7dtBlxFk?si=zh1EPSy-Z79_eTTK

<br/>

## âš¡ Features

| Feature | Description |
|---------|-------------|
| ðŸ  **Homepage** | Hero section with featured products and category navigation |
| ðŸ‘• **Product Catalog** | Browse products by Men's and Women's categories |
| ðŸ” **Search** | Full-text search across product names, categories & descriptions |
| ðŸ›ï¸ **Shopping Cart** | Session-based cart with add, update quantity & remove |
| ðŸ’³ **Checkout** | Stripe-hosted Checkout (test mode), bKash, Nagad & Cash on Delivery |
| ðŸ§¾ **Invoice** | Order confirmation with invoice details |
| ðŸ‘¤ **User Accounts** | Registration, login & email verification |
| ðŸŽ¨ **Product Variants** | Color and size variants with variant-based pricing |
| ðŸ–¼ï¸ **Image Gallery** | Multiple images per product with Cloudinary storage |
| ðŸ“± **Responsive Design** | Mobile-first UI with Bootstrap |
| ðŸ” **Admin Panel** | Django admin for full CRUD on products, orders & users |

<br/>

## ðŸ› ï¸ Tech Stack

<div align="center">

| Layer | Technology |
|-------|-----------|
| **Backend** | Django 5.2 Â· Gunicorn |
| **Database** | PostgreSQL (via dj-database-url) |
| **Media Storage** | Cloudinary |
| **Static Files** | WhiteNoise |
| **Frontend** | Bootstrap Â· jQuery Â· Font Awesome |
| **Deployment** | Render.com |

</div>

<br/>

## ðŸ“ Project Structure

```
Ecommerce_Storefront/
â”‚
â”œâ”€â”€ Ecommerce_Storefront/    # Django project settings & config
â”‚   â”œâ”€â”€ settings.py
â”‚   â”œâ”€â”€ urls.py
â”‚   â””â”€â”€ wsgi.py
â”‚
â”œâ”€â”€ home/                    # Homepage & contact page
â”œâ”€â”€ products/                # Product catalog, cart, checkout & orders
â”œâ”€â”€ accounts/                # User auth, profiles & email verification
â”œâ”€â”€ base/                    # Shared base model & email utilities
â”‚
â”œâ”€â”€ templates/               # HTML templates
â”‚   â”œâ”€â”€ base/                #   â””â”€ base layout, sidebar, alerts
â”‚   â”œâ”€â”€ home/                #   â””â”€ index, contact
â”‚   â”œâ”€â”€ product/             #   â””â”€ product detail, cart, checkout, invoice, search
â”‚   â””â”€â”€ accounts/            #   â””â”€ login, register
â”‚
â”œâ”€â”€ public/static/           # CSS, JS, fonts & images
â”œâ”€â”€ build.sh                 # Render build script
â”œâ”€â”€ manage.py
â””â”€â”€ requirements.txt
```

<br/>

## ðŸš€ Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL (or use SQLite for local dev)
- Cloudinary account (for media uploads)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/<NaimurRahmannn>/Ecommerce_Storefront.git
cd Ecommerce_Storefront

# 2. Create & activate virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
#    Create a .env file or export these:
export SECRET_KEY="your-secret-key"
export DATABASE_URL="postgres://user:pass@host:5432/dbname"
export CLOUD_NAME="your-cloudinary-cloud"
export API_KEY="your-cloudinary-key"
export API_SECRET="your-cloudinary-secret"

# 5. Apply migrations
python manage.py migrate

# 6. Create a superuser
python manage.py createsuperuser

# 7. Run the development server
python manage.py runserver
```

Visit **http://127.0.0.1:8000** and start exploring! ðŸŽ‰

<br/>

## ðŸŒ Deployment (Render)

This project is production-ready for **Render.com**:

1. Connect your GitHub repo to Render
2. Set **Build Command** â†’ `./build.sh`
3. Set **Start Command** â†’ `gunicorn Ecommerce_Storefront.wsgi`
4. Add the environment variables listed above
5. Deploy! ðŸš€

<br/>

## ðŸ“¦ Environment Variables

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret key |
| `DATABASE_URL` | PostgreSQL connection string |
| `CLOUD_NAME` | Cloudinary cloud name |
| `API_KEY` | Cloudinary API key |
| `API_SECRET` | Cloudinary API secret |
| `GOOGLE_CLIENT_ID` | Google OAuth web client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `STRIPE_PUBLIC_KEY` | Stripe publishable key (must start with `pk_test_`) |
| `STRIPE_SECRET_KEY` | Stripe secret key (must start with `sk_test_`) |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret (must start with `whsec_`) |
| `STRIPE_CURRENCY` | Charge currency sent to Stripe (set to `usd`) |
| `STRIPE_BDT_PER_USD` | BDT-to-USD exchange rate (e.g. `120.50`) |

See `.env.example` for a full template.

<br/>

### Google OAuth

Create a Web application OAuth client in Google Cloud Console and add every callback URL used by the application as an exact **Authorized redirect URI**:

```text
http://127.0.0.1:8000/accounts/google/login/callback/
http://localhost:8000/accounts/google/login/callback/
https://haatify.onrender.com/accounts/google/login/callback/
```

Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in the local `.env` file and in the production environment. The Google sign-in button is hidden when either value is missing.

<br/>

### Stripe Test Mode

Stripe Checkout is enabled only when all five Stripe environment variables are set and keys use test-mode prefixes (`pk_test_`, `sk_test_`, `whsec_`). The checkout tab is hidden when Stripe is disabled.

#### Getting Test Mode Keys

1. Go to the [Stripe Dashboard → Test Mode → API Keys](https://dashboard.stripe.com/test/apikeys).
2. Copy the **Publishable key** (`pk_test_...`) → `STRIPE_PUBLIC_KEY`.
3. Copy the **Secret key** (`sk_test_...`) → `STRIPE_SECRET_KEY`.

#### Local Webhook Forwarding (Stripe CLI)

The local CLI signing secret is **different** from the Dashboard endpoint secret.

```bash
# Install the Stripe CLI, then:
stripe listen --forward-to localhost:8000/payments/webhook/
```

The CLI prints a signing secret (`whsec_...`). Set it as `STRIPE_WEBHOOK_SECRET` in your `.env`.

#### Deployed Webhook (Render)

In the [Stripe Dashboard → Webhooks](https://dashboard.stripe.com/test/webhooks):

1. Add endpoint: `https://haatify.onrender.com/payments/webhook/`
2. Subscribe to these events:
   - `checkout.session.completed`
   - `checkout.session.async_payment_succeeded`
   - `checkout.session.async_payment_failed`
   - `checkout.session.expired`
   - `payment_intent.payment_failed`
   - `charge.refunded`
3. Copy the endpoint signing secret → set as `STRIPE_WEBHOOK_SECRET` in Render environment.

> **Note:** The local CLI signing secret and the Dashboard endpoint signing secret are different values. Use the correct one for each environment.

#### Test Cards

| Scenario | Card Number | Expiry | CVC |
|----------|-------------|--------|-----|
| Successful payment | `4242 4242 4242 4242` | Any future date | Any 3 digits |
| Requires authentication | `4000 0025 0000 3155` | Any future date | Any 3 digits |
| Declined | `4000 0000 0000 0002` | Any future date | Any 3 digits |

#### Debugging Webhook Deliveries

Check the [Stripe Dashboard → Webhooks → Recent Deliveries](https://dashboard.stripe.com/test/webhooks) for:
- HTTP status code (should be `200`)
- Request/response payloads
- Retry schedule (Stripe retries failed deliveries for up to 72 hours)

<br/>


## ðŸ¤ Contributing

Contributions are welcome! Feel free to open an issue or submit a pull request.

1. Fork the project
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

<br/>

---

<div align="center">

**Built with â¤ï¸ using Django**

â­ Star this repo if you found it helpful!

</div>
