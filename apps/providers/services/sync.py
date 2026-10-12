"""Read-only Stripe sandbox imports. Provider timestamps are never staged."""

from datetime import UTC, datetime, timedelta

import stripe
from django.db import transaction
from django.utils import timezone

from apps.ops_disputes.models import Dispute, EvidenceItem
from apps.ops_refunds.models import Customer, Order, PaymentTransaction, Refund
from apps.ops_refunds.services.risk import apply_risk
from apps.providers.models import ProviderConnection

stripe.default_http_client = stripe.RequestsClient(timeout=15)


def _stripe_key(conn):
    key = conn.get_credentials().get("secret_key", "")
    if not key.startswith("sk_test_"):
        raise ValueError("FinOps requires a Stripe sandbox secret key (sk_test_).")
    return key


def _options(conn):
    return {"api_key": _stripe_key(conn)}


def stripe_test_connection(conn):
    return stripe.Account.retrieve(**_options(conn)).to_dict()


def _time(value):
    return datetime.fromtimestamp(int(value), tz=UTC) if value else timezone.now()


def _sandbox(obj):
    if obj.get("livemode") is not False:
        raise ValueError("Only sandbox records can be imported.")


def import_charge(conn, ch):
    ch = ch if isinstance(ch, dict) else ch.to_dict()
    _sandbox(ch)
    billing = ch.get("billing_details") or {}
    email = billing.get("email") or ch.get("receipt_email") or ""
    # A Stripe customer ID identifies the customer; absent that, do not merge unrelated charges.
    identity = ch.get("customer") or f"charge:{ch['id']}"
    customer, _ = Customer.objects.update_or_create(
        workspace=conn.workspace,
        external_id=identity,
        defaults={
            "email": email,
            "name": billing.get("name") or "",
            "raw_payload": {"stripe_customer": ch.get("customer")},
        },
    )
    values = {
        "provider": "stripe",
        "customer": customer,
        "amount": int(ch["amount"]),
        "currency": ch["currency"].upper(),
        "raw_payload": dict(ch),
    }
    order, _ = Order.objects.update_or_create(
        workspace=conn.workspace,
        external_id=ch["id"],
        defaults={
            **values,
            "status": "paid" if ch.get("paid") else "unpaid",
            "created_at": _time(ch.get("created")),
        },
    )
    payment, _ = PaymentTransaction.objects.update_or_create(
        workspace=conn.workspace,
        external_id=ch["id"],
        defaults={
            **values,
            "order": order,
            "status": ch.get("status", "unknown"),
            "initiated_at": _time(ch.get("created")),
            "updated_at": timezone.now(),
        },
    )
    return payment


def _payment(conn, charge_id):
    # Retrieve current provider state, including charges older than the import window.
    return (
        import_charge(conn, stripe.Charge.retrieve(charge_id, **_options(conn)))
        if charge_id
        else None
    )


def import_refund(conn, obj):
    obj = obj if isinstance(obj, dict) else obj.to_dict()
    _sandbox(obj)
    payment = _payment(conn, obj.get("charge"))
    refund, _ = Refund.objects.update_or_create(
        workspace=conn.workspace,
        external_id=obj["id"],
        defaults={
            "provider": "stripe",
            "transaction": payment,
            "order": payment.order if payment else None,
            "customer": payment.customer if payment else None,
            "amount": int(obj["amount"]),
            "currency": obj["currency"].upper(),
            "status": obj["status"],
            "initiated_at": _time(obj.get("created")),
            "raw_payload": dict(obj),
            "last_provider_update_at": timezone.now(),
        },
    )
    apply_risk(refund, conn.workspace.sla_days)
    return refund


def import_dispute(conn, obj):
    obj = obj if isinstance(obj, dict) else obj.to_dict()
    _sandbox(obj)
    payment = _payment(conn, obj.get("charge"))
    deadline = (obj.get("evidence_details") or {}).get("due_by")
    dispute, _ = Dispute.objects.update_or_create(
        workspace=conn.workspace,
        external_id=obj["id"],
        defaults={
            "provider": "stripe",
            "transaction": payment,
            "order": payment.order if payment else None,
            "customer": payment.customer if payment else None,
            "amount": int(obj["amount"]),
            "currency": obj["currency"].upper(),
            "status": obj["status"],
            "reason": obj.get("reason", ""),
            "created_at": _time(obj.get("created")),
            "deadline_at": _time(deadline) if deadline else None,
            "raw_payload": dict(obj),
        },
    )
    for kind in ["policy", "customer_comms", "delivery_proof", "refund_proof"]:
        EvidenceItem.objects.get_or_create(dispute=dispute, type=kind)
    return dispute


def stripe_sync_last_days(conn, *, days=30):
    conn.last_sync_attempt_at = timezone.now()
    conn.save(update_fields=["last_sync_attempt_at"])
    try:
        with transaction.atomic():
            conn = (
                ProviderConnection.objects.select_for_update()
                .select_related("workspace")
                .get(pk=conn.pk)
            )
            since = int((timezone.now() - timedelta(days=days)).timestamp())
            options = _options(conn)
            counts = {"transactions": 0, "refunds": 0, "disputes": 0}
            for resource, importer, counter in [
                (stripe.Charge, import_charge, "transactions"),
                (stripe.Refund, import_refund, "refunds"),
                (stripe.Dispute, import_dispute, "disputes"),
            ]:
                seen = set()
                for obj in resource.list(
                    limit=100, created={"gte": since}, **options
                ).auto_paging_iter():
                    importer(conn, obj)
                    seen.add(obj["id"])
                    counts[counter] += 1
                # Also refresh unresolved cases first imported outside the window.
                model = {"refunds": Refund, "disputes": Dispute}.get(counter)
                if model:
                    terminal = (
                        {"succeeded", "canceled", "cancelled"}
                        if model is Refund
                        else {"won", "lost", "warning_closed"}
                    )
                    ids = (
                        model.objects.filter(workspace=conn.workspace, provider="stripe")
                        .exclude(status__in=terminal)
                        .values_list("external_id", flat=True)
                    )
                    for object_id in ids:
                        if object_id not in seen:
                            importer(conn, resource.retrieve(object_id, **options))
                            counts[counter] += 1
            conn.last_sync_at = timezone.now()
            conn.sync_error = ""
            conn.status = ProviderConnection.STATUS_CONNECTED
            conn.save(update_fields=["last_sync_at", "sync_error", "status"])
        return counts
    except Exception:
        ProviderConnection.objects.filter(pk=conn.pk).update(
            sync_error="Stripe synchronization failed. Check credentials and network, then retry."
        )
        raise


def refresh_event(conn, event):
    """Fetch authoritative current state instead of applying potentially out-of-order payloads."""
    kind = event["type"]
    object_id = event["data"]["object"]["id"]
    if kind.startswith("charge.dispute."):
        import_dispute(conn, stripe.Dispute.retrieve(object_id, **_options(conn)))
    elif kind in {"refund.created", "refund.updated", "refund.failed"}:
        import_refund(conn, stripe.Refund.retrieve(object_id, **_options(conn)))
    elif kind in {"charge.succeeded", "charge.failed", "charge.updated", "charge.refunded"}:
        import_charge(conn, stripe.Charge.retrieve(object_id, **_options(conn)))
