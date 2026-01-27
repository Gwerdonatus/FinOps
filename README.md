# FinOps Ops Console  
### Refund & Dispute Operations Dashboard (Demo-Ready)

FinOps Ops Console is an **operations-focused fintech dashboard** designed to help merchants and support teams **track refunds early, manage risk, and prevent chargebacks** before revenue is lost.

This project was built to explore a real operational gap in payment platforms:  
refunds are time-sensitive, but most teams only react *after* problems escalate.

---

## Why This Exists (Problem Statement)

In most payment stacks (Stripe, Shopify, Paystack):

- Refunds arrive as **emails or isolated events**
- There is no clear **refund deadline visibility**
- Teams don’t know which refunds are **about to become disputes**
- Searching across customer, transaction, refund, and order data is fragmented
- By the time a dispute appears, **the damage is already done**

Most chargebacks are not fraud —  
they happen because **refunds were missed or delayed**.

**FinOps Ops Console treats refunds as an operational workflow, not just a payment event.**

---

## What This Project Does

FinOps Ops Console provides a **single operational view** for refund and dispute risk across payment providers.

### Core Capabilities

- Refund SLA tracking with clear risk states
- Automated risk classification:
  - `SAFE`
  - `DUE_SOON`
  - `AT_RISK`
  - `OVERDUE`
- Alerting system for time-sensitive refunds
- Universal search across:
  - Customer email
  - Transaction ID
  - Refund ID
  - Order ID
- Provider demo seeding for realistic testing and screen recordings

---

## Project Phases Overview

### Phase 1 — Foundation
- Django project scaffold
- Authentication + workspace scoping
- Core domain models (transactions, refunds, alerts)
- Clean app-based architecture

---

### Phase 2 — Ops UX + Risk Logic
- Public marketing landing page (`/`)
- Tailwind-styled UI (via CDN for fast iteration)
- Refund SLA logic
- Refund risk states:
  - SAFE
  - DUE_SOON
  - AT_RISK
  - OVERDUE
- Alerts feed for due-soon and overdue refunds
- Universal search (by email or ID)
- Minimal dispute context page (checklist-style)

> At this stage, the system already behaves like a real ops tool — even without live providers.

---

### Phase 3 — Planned
- Background jobs (Celery + Redis)
- Evidence uploads + PDF exports
- Webhook-driven updates
- Deeper dispute workflows

---

### Phase 4 — Provider Connections + Demo Mode (Implemented)

This phase makes the project **fully demo-ready**.

- Provider connections UI (Stripe, Shopify, Paystack)
- Encrypted credential storage
- Stripe demo seeding:
  - Generates 250 Stripe test payments
  - Automatically creates refunds
  - Syncs everything into the dashboard
  - Time-shifts refunds to naturally produce:
    - SAFE
    - DUE_SOON
    - AT_RISK
    - OVERDUE
- Alerts trigger automatically based on risk state

This allows **realistic demos without mocked data**.

---

## Tech Stack

### Backend
- **Django**
- **PostgreSQL** (SQLite fallback)
- **Stripe API**
- Encrypted provider credentials
- Time-based risk modeling
- Idempotent sync logic

### Frontend
- Django Templates
- Tailwind CSS (CDN)
- Dashboard-first UX
- Alert-driven navigation

### Infrastructure & Tooling
- Docker & Docker Compose
- Redis (included, optional for now)
- Pytest
- Environment-based configuration

---

## Local Setup

### 1) Clone or unzip

```bash
mkdir -p finops_console
cd finops_console
code .
![Screenshot_27-1-2026_19759_127 0 0 1](https://github.com/user-attachments/assets/a1ee2c08-bfc4-4b88-b725-e532d88ba25b)
