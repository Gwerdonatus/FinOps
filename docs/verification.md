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
- Ruff, Black, Django check and missing-migration checks pass. Full suite: 20 passing tests, 64.01% application coverage, above the existing 60% CI gate.

No external Stripe or other payment-provider mutations were performed. This is not a production deployment, automatic provider submission or completed file-upload workflow.
