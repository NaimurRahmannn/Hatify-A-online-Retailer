<div align="center">

# 🛒 Haatify — E-Commerce Storefront

### A modern, full-featured e-commerce platform built with Django

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-5.2-092E20?style=for-the-badge&logo=django&logoColor=white)](https://djangoproject.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Render](https://img.shields.io/badge/Deployed_on-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://haatify.onrender.com)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

<br/>

**[🌐 Live Demo](https://haatify.onrender.com)** &nbsp;·&nbsp; **[🐛 Report Bug](../../issues)** &nbsp;·&nbsp; **[✨ Request Feature](../../issues)**

---

</div>

## 📖 About

**Haatify** is a clean, responsive e-commerce storefront designed for fashion retail. It supports product browsing by categories (Men & Women), shopping cart management, order checkout with multiple payment options, user authentication, and an admin dashboard for managing inventory.

<br/>

## 🎬 Project Video

- YouTube Demo: https://youtu.be/06E7dtBlxFk?si=zh1EPSy-Z79_eTTK

<br/>

## ⚡ Features

| Feature | Description |
|---------|-------------|
| 🏠 **Homepage** | Hero section with featured products and category navigation |
| 👕 **Product Catalog** | Browse products by Men's and Women's categories |
| 🔍 **Search** | Full-text search across product names, categories & descriptions |
| 🛍️ **Shopping Cart** | Session-based cart with add, update quantity & remove |
| 💳 **Checkout** | Order placement with Card, bKash, Nagad & Cash on Delivery |
| 🧾 **Invoice** | Order confirmation with invoice details |
| 👤 **User Accounts** | Registration, login & email verification |
| 🎨 **Product Variants** | Color and size variants with variant-based pricing |
| 🖼️ **Image Gallery** | Multiple images per product with Cloudinary storage |
| 📱 **Responsive Design** | Mobile-first UI with Bootstrap |
| 🔐 **Admin Panel** | Django admin for full CRUD on products, orders & users |

<br/>

## 🛠️ Tech Stack

<div align="center">

| Layer | Technology |
|-------|-----------|
| **Backend** | Django 5.2 · Gunicorn |
| **Database** | PostgreSQL (via dj-database-url) |
| **Media Storage** | Cloudinary |
| **Static Files** | WhiteNoise |
| **Frontend** | Bootstrap · jQuery · Font Awesome |
| **Deployment** | Render.com |

</div>

<br/>

## 📁 Project Structure

```
Ecommerce_Storefront/
│
├── Ecommerce_Storefront/    # Django project settings & config
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── home/                    # Homepage & contact page
├── products/                # Product catalog, cart, checkout & orders
├── accounts/                # User auth, profiles & email verification
├── base/                    # Shared base model & email utilities
│
├── templates/               # HTML templates
│   ├── base/                #   └─ base layout, sidebar, alerts
│   ├── home/                #   └─ index, contact
│   ├── product/             #   └─ product detail, cart, checkout, invoice, search
│   └── accounts/            #   └─ login, register
│
├── public/static/           # CSS, JS, fonts & images
├── build.sh                 # Render build script
├── manage.py
└── requirements.txt
```

<br/>

## 🚀 Getting Started

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

Visit **http://127.0.0.1:8000** and start exploring! 🎉

<br/>

## 🌍 Deployment (Render)

This project is production-ready for **Render.com**:

1. Connect your GitHub repo to Render
2. Set **Build Command** → `./build.sh`
3. Set **Start Command** → `gunicorn Ecommerce_Storefront.wsgi`
4. Add the environment variables listed above
5. Deploy! 🚀

<br/>

## 📦 Environment Variables

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret key |
| `DATABASE_URL` | PostgreSQL connection string |
| `CLOUD_NAME` | Cloudinary cloud name |
| `API_KEY` | Cloudinary API key |
| `API_SECRET` | Cloudinary API secret |
| `GOOGLE_CLIENT_ID` | Google OAuth web client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |

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

## 🤝 Contributing

Contributions are welcome! Feel free to open an issue or submit a pull request.

1. Fork the project
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

<br/>

---

<div align="center">

**Built with ❤️ using Django**

⭐ Star this repo if you found it helpful!

</div>
