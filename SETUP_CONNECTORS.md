# Connector setup (Stripe / Shopify / Paystack)

This repo supports **real provider connections**. For the demo video you can connect Stripe in **test mode** and generate demo data.

## Stripe (recommended for demo)

1. Create a Stripe account (or use an existing one).
2. Switch to **Developers → API keys** and copy your **test** secret key (`sk_test_...`).
3. In the app: **Connections → Stripe → Save key**
4. (Demo) Click **Generate 250 demo transactions**. This creates Stripe test objects and auto-syncs them.

## Shopify (token-based, no OAuth required for MVP)

This uses a standard Shopify pattern: a **Custom App** with an Admin API token.

1. In Shopify admin: **Settings → Apps and sales channels → Develop apps**
2. Create a **Custom App**
3. Configure **Admin API scopes** (minimum for read-only demo):
   - `read_orders`
   - `read_customers`
4. Install the app and copy the **Admin API access token** (`shpat_...`)
5. In the app: **Connections → Shopify**
   - Shop domain: `your-store.myshopify.com`
   - Admin token: `shpat_...`
   - Click **Test**

## Paystack (token-based)

1. In Paystack dashboard: **Settings → API Keys & Webhooks**
2. Copy your **test** secret key (`sk_test_...`) for demo/dev.
3. In the app: **Connections → Paystack → Save key → Test**

## Security

Provider credentials are stored encrypted using Fernet (`cryptography`). Set `ENCRYPTION_KEY` in `.env`:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Then put that output into:

```env
ENCRYPTION_KEY=...
```

**Never commit real keys** to GitHub.
