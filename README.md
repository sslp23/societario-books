# Livros App

A web application for managing **Livros de Registro de Ações Nominativas** — the official Brazilian corporate share register. Built with [Reflex](https://reflex.dev) (Python full-stack) and PostgreSQL.

---

## Features

- **Multi-tenant** — each organization has its own isolated data
- **Livros (Registers)** — create and manage multiple share registers per organization
- **Lançamentos (Entries)** — record share transactions with all legally required fields:
  - Data do Registro
  - Tipo de Ação (ON, PN, PNA, PNB)
  - Classe da Ação
  - Quantidade de Ações
  - Natureza da Operação (Subscrição, Compra e Venda, Doação, Herança, Dação em Pagamento)
  - Certificado
  - Capital Realizado / Valor a Pagar
  - Averbações / Ônus (Penhor, Usufruto, Fideicomisso, Alienação Fiduciária)
  - Assinatura / Log Eletrônico (e-CPF / e-CNPJ)
- **PDF Export** — downloads the full register as a landscape A4 table

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | [Reflex](https://reflex.dev) 0.8.x (Python) |
| Database | PostgreSQL via [Neon](https://neon.tech) |
| ORM | SQLModel + SQLAlchemy |
| PDF generation | fpdf2 |
| Auth | bcrypt password hashing |

---

## Project Structure

```
livros_app/
├── livros_app/
│   ├── livros_app.py   # App state, event handlers, UI components
│   └── models.py       # Database models (User, Book, BookEntry)
├── assets/             # Static assets (favicon, etc.)
├── rxconfig.py         # Reflex config + DB URL  ← gitignored
├── seed_user.py        # One-time user creation script  ← gitignored
├── .gitignore
└── README.md
```

### Database Models

```
User            — login credentials, tied to an organization
Book            — a Livro de Registro (container)
BookEntry       — a single lançamento within a Book
                  book_id → Book.id (ON DELETE CASCADE)
```

---

## Local Development Setup

### 1. Install dependencies

```bash
pip install reflex fpdf2 bcrypt psycopg2-binary
```

### 2. Create `rxconfig.py`

This file is gitignored. Create it in the project root:

```python
import os
import reflex as rx

config = rx.Config(
    app_name="livros_app",
    db_url=os.environ.get(
        "DATABASE_URL",
        "postgresql://user:password@host/dbname?sslmode=require",
    ),
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)
```

Replace the fallback connection string with your actual Neon (or local PostgreSQL) URL.

### 3. Set up the database

```bash
reflex db init
reflex db makemigrations --message "initial schema"
reflex db migrate
```

### 4. Create the first user

Create `seed_user.py` (also gitignored) in the project root:

```python
import bcrypt
import reflex as rx
from livros_app.models import User
from sqlalchemy import select

USERNAME = "admin"
PASSWORD = "your_password"
ORGANIZATION = "your_org"

hash = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
with rx.session() as session:
    if not session.exec(select(User).where(User.username == USERNAME)).first():
        session.add(User(username=USERNAME, password_hash=hash, organization=ORGANIZATION))
        session.commit()
        print(f"User '{USERNAME}' created.")
    else:
        print("User already exists.")
```

```bash
python seed_user.py
```

Delete the file after use — it contains plaintext credentials.

### 5. Run

```bash
reflex run
```

Open [http://localhost:3000](http://localhost:3000).

---

## Adding More Users

Recreate `seed_user.py` with the new user's details and run it again. Multiple users can share the same `ORGANIZATION` and will see the same books, or use different organizations for full isolation.

---

## Deployment

### Environment variable

Set `DATABASE_URL` as a secret in your deployment platform. The app reads it automatically via `os.environ.get("DATABASE_URL", ...)` in `rxconfig.py`.

### Reflex Cloud (recommended)

```bash
reflex deploy
```

Create an account at [cloud.reflex.dev](https://cloud.reflex.dev) first.

### Railway / Render

Connect your GitHub repository and set the `DATABASE_URL` environment variable in the platform dashboard.

> **Note:** PDF export currently saves files to `.web/public/` which works in local development. A cloud storage solution (e.g. Cloudflare R2) is needed for production PDF serving.

---

## Known Limitations

- PDF export uses local filesystem — requires adaptation for production deployment
- No password reset flow — user management is done via `seed_user.py`
- SQLite FK cascade does not enforce on Windows dev without `PRAGMA foreign_keys = ON`
