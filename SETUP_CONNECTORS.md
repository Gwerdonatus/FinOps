# Connector scope

## Stripe sandbox

FinOps imports existing sandbox charges, refunds and disputes. It creates no provider payments, refunds or dispute submissions. An admin saves a `sk_test_` key in Connections, selects Test to verify the account, then Sync. The periodic worker repeats synchronization every five minutes. Status includes account ID, last attempt, last success and sanitized errors.

Webhook route: `/webhooks/stripe/<connection_id>/`. Configure the endpoint's own signing secret in the Stripe card. A local endpoint requires Stripe CLI forwarding; a hosted endpoint requires HTTPS. Do not reuse a different application's signing secret. Duplicate signed events are deduplicated; current resource state is fetched from Stripe.

Existing sandbox credentials were reused locally with the owner's authorization. Read-only import returned three payments and no refunds/disputes. Other staged cases remain synthetic. External delivery is not configured; signed local delivery and retry behavior are tested.

## OpenAI

Admins configure a key in Connections → OpenAI case briefs. Each case asks for explicit source sharing before generation. This environment intentionally has no OpenAI key yet; API transport/schema/error paths are tested with mocked responses.

## Other providers

Shopify and Paystack retain existing credential/test/list adapters. Full record imports are unfinished. PayPal is a placeholder. Neither adapter is part of the verified Stripe release.
