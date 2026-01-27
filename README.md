# FinOps Ops Console (Phase 1 + Phase 2)

This repo includes:

- **Phase 1 foundation**: Django project scaffold, auth, workspace scoping middleware, placeholder modules.
- **Phase 2 upgrades (demo-ready)**:
  - Public marketing homepage (landing page) at `/`
  - Tailwind-styled UI (via CDN) for clean screen recordings
  - Refund SLA risk states (SAFE / DUE_SOON / AT_RISK / OVERDUE)
  - Alerts feed for **due soon** + **overdue** refunds
  - Universal search (by ID or customer email)
  - Minimal dispute context page + evidence checklist (no uploads/exports yet)

> Provider integrations, background jobs, PDF exports are intentionally **not** included yet.

---

## 1) Local setup (Bash)

### 1.1 Create folder + open in VS Code

```bash
# Create a folder anywhere you want
mkdir -p finops_console
cd finops_console

# (Option A) If you downloaded the zip, unzip it here
# unzip finops_console_phase12.zip

# Open in VS Code (make sure `code` command is enabled)
code .
```

If `code .` doesn't work:

- In VS Code: press **Ctrl+Shift+P** → type **Shell Command: Install 'code' command in PATH** → run it.
- Restart your terminal, then run `code .` again.

---

## 2) Python + venv

```bash
python3 --version   # should be 3.11+
python3 -m venv .venv
source .venv/bin/activate

pip install -U pip
pip install -e ".[dev]"
```

---

## 3) Environment variables

```bash
cp .env.example .env
```

You can run on SQLite (default) or Postgres (recommended for realism).  
If you want Postgres, continue to section 4.

---

## 4) Postgres + Redis (docker-compose)

```bash
docker compose up -d
```

This starts:

- Postgres on `localhost:5432`
- Redis on `localhost:6379` (included but not used yet)

If you use docker Postgres, ensure `.env` has:

```
DATABASE_URL=postgres://finops:finops@127.0.0.1:5432/finops_console
```

---

## 5) Migrations + seed data (demo user)

```bash
python manage.py migrate
python manage.py seed_dev
```

Demo credentials:

- **Username**: `demo@finops.local`
- **Password**: `demo1234`

---

## 6) Run the server

```bash
python manage.py runserver
```

Open:

- Public landing page: `http://127.0.0.1:8000/`
- Login: `http://127.0.0.1:8000/login/`
- App dashboard: `http://127.0.0.1:8000/app/`

---

## 7) Run tests

```bash
pytest
```

---

## 8) Useful commands

Recalculate refund risk (and create alerts):

```bash
python manage.py shell -c "from apps.workspaces.models import Workspace; from apps.ops_refunds.services.risk import recalc_refund_risk_for_workspace; ws=Workspace.objects.first(); recalc_refund_risk_for_workspace(ws); print('done')"
```

---

## Routes

- `/` → marketing landing page
- `/login/` → login
- `/app/` → dashboard
- `/app/refunds/` → refund list + detail pages
- `/app/search/` → unified search
- `/app/alerts/` → alerts feed
- `/app/disputes/` → dispute list + detail (checklist)

---

## What’s next (Phase 3)

- Real provider integrations (Stripe/Paystack/Shopify)
- Evidence uploads + exportable evidence packs (PDF)
- Async jobs + scheduled checks (Celery/Redis)


## Phase 4: Provider Connections + Demo Seed (Option 1)

- Set `DEMO_MODE=1` and generate an `ENCRYPTION_KEY` in `.env`.
- Go to **Connections** in the app nav.
- Add a **Stripe test secret key** (`sk_test_...`).
- Click **Generate 250 demo transactions** to create Stripe test objects, then auto-sync them.
- Dashboard + Refunds + Alerts will populate and become demo-ready.

### Generate ENCRYPTION_KEY

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
# FinOps
