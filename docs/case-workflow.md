# Case-workflow decisions

## Stripe is a read-only sandbox source

Only `sk_test_` credentials and records with `livemode=false` are accepted. Each SDK call receives its connection key explicitly; one workspace cannot change a global API key used by another. Provider-side demo payment/refund generation is disabled. Original provider timestamps remain unchanged even with DEMO_MODE enabled.

A five-minute worker imports the last 30 days and refreshes older unresolved refunds/disputes already known to FinOps. Associated charges are retrieved even outside that window. Import updates are transactional; a failed cycle preserves the previous successful timestamp and displays a sanitized retry message. This is a small-workspace synchronous importer, not a benchmarked high-volume ingestion pipeline.

Webhook signatures use the raw request body. Live events are rejected. Connection-row locking serializes imports and webhook updates; unique event receipts prevent duplicate deliveries. Receipts roll back when processing fails. The event's referenced resource is retrieved from Stripe rather than applying a potentially stale event snapshot. No financial mutations are available. Signed local delivery was verified; external delivery has not been configured.

## Evidence remains untrusted

PDF, PNG, JPEG and UTF-8 text uploads are limited to 5 MB and 10 files per checklist item. Extensions and content signatures are checked; this is not antivirus or complete document-format validation. Server-generated storage paths prevent filename traversal. Downloads require membership in the same active workspace, force attachment handling and disable caching. Raw media paths are not publicly routed. Each attachment records size and SHA256.

Uploading sets the checklist to attached/awaiting review. An operator can subsequently mark it reviewed or not applicable. Text attachments expose at most 12,000 characters locally; AI receives at most 2,000 per source. PDF/image extraction and OCR are deliberately not claimed.

## AI drafts supplement deterministic facts

Amounts, deadlines, provider status and risk calculations remain ordinary application logic. A source-based brief is always available. OpenAI receives bounded source text only after explicit case-level sharing consent. Credentials are encrypted at rest and configured by workspace admins. No tools, refunds or evidence-submission actions are exposed to the model.

The Responses request uses a strict JSON schema and `store=false`. Each generated observation or investigation step must include a known source ID and an exact quote from that source; malformed results, refusal, truncation and network failures produce no saved draft. Exact quotes do not establish semantic correctness. All interpretations need human review.

The source snapshot, model and fingerprint are saved for provenance. Unchanged requests reuse a previous result; changed sources flag old drafts as stale. Per-case recent-generation throttling limits accidental repeats, but concurrent generation/global budgets require stronger controls before production.

Official references: [Stripe webhooks](https://docs.stripe.com/webhooks), [Stripe disputes](https://docs.stripe.com/api/disputes), [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [Responses storage controls](https://developers.openai.com/api/docs/guides/migrate-to-responses).

## Next production work

Compiled frontend assets, HTTPS, monitored queues, credential rotation/removal, storage retention and malware scanning, provider-triggered external webhook tests, a real-model evaluation set, and measured handling-time improvements. No dispute-win probability or prevention claim is made.
