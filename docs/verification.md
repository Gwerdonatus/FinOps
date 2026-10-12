# Local verification

## Environment

Apple Silicon Mac, Python 3.12 container, Django 5.2, PostgreSQL 16. App at localhost:8300. Existing Sentinel and Drift Recon services were preserved.

## Scenario verified

- Migrations and static collection complete at startup.
- Seed repeated twice: four refund cases, one dispute, four checklist items and three alerts; no duplicated scenario rows.
- Browser demo login works.
- Dashboard has one case in each risk state; overdue filter isolates the $180 USD case and shows its linked customer, order and payment.
- Dispute review saved and persisted. PDF includes the saved note and explicitly labels synthetic data and incomplete evidence.
- Refund PDF and dispute PDF generated and downloaded from authenticated views. Both rendered and inspected with no clipping or overlap.
- Overdue CSV generation succeeds and retains minor-unit amounts in its documented schema.
- Risk worker completes minute-by-minute refreshes without duplicate state-change alerts.
- Ruff, Black, Django check and missing-migration checks pass. Full suite: 42 passing tests, 75.93% application coverage, above the existing 60% CI gate.

No external Stripe or other payment-provider mutations were performed. This is not a production deployment or automatic provider submission.

## Case workflow release

- Existing Stripe sandbox verified: account acct_1Q7Ff1Rwkn46vgfA, three imported test payments, zero available refunds/disputes. Periodic worker repeats imports without duplicate records.
- Signed local webhook HTTP delivery returns 200; duplicate delivery returns 200 with one receipt. Processing retrieves current Stripe state. External Stripe forwarding is not configured.
- Synthetic customer-message text uploaded through the browser, stored privately and visible in the case's source brief. Review notes saved. Authenticated file downloads, workspace isolation, content/type/size restrictions and path traversal rejection are covered by tests.
- OpenAI generation remains unconfigured at the owner's request. Mocked Responses API checks cover strict schema, no storage/tools, validated quotes, caching, refusals, changed sources and explicit sharing consent. No live-model quality or latency claim is made.
- Private attachments survive container recreation through the media volume. PDF summaries now list attachment references/checksums. The updated one-page synthetic evidence PDF was rendered and visually checked with no clipping or overlap.
