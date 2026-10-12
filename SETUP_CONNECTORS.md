# Provider connector scope

The local recruiter demo uses synthetic records and needs no provider credentials.

## Stripe

Connections lets a workspace store an encrypted Stripe credential, test account access and manually synchronize payment/refund records. Saving a key does not mark the provider connected; a successful test does.

Use sandbox credentials for demonstrations. The optional 250-payment seed creates external Stripe test objects and test refunds; it is separate from `python manage.py seed_demo`. It is not required for the local walkthrough and should not be mistaken for production activity. Its time-shifted refund deadlines are staged.

Live connection code exists but is not covered by this local demo's runtime verification. Do not use this prototype to administer live funds without further hardening.

## Shopify and Paystack

Credential validation and provider read/list adapters exist. Complete import into the refund/dispute domain is not implemented; the UI labels these limits. PayPal is a placeholder. These providers are not represented as working end-to-end integrations.

## Credential handling

Set a Fernet `ENCRYPTION_KEY` in ignored `.env`. Stored connection credentials are encrypted in PostgreSQL. Keep a secure backup of the key; replacing it without migration makes existing credentials unreadable. Do not expose keys in screenshots, commit them or put them in URLs.
