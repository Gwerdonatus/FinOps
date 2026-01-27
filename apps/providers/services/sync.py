from __future__ import annotations

import datetime as dt
import random
from typing import Tuple

import stripe
from django.conf import settings
from django.utils import timezone

from apps.ops_refunds.models import Customer, Order, PaymentTransaction, Refund
from apps.providers.models import ProviderConnection


# =========================================================
# Risk + Alerts helpers (DEMO-friendly + deterministic)
# =========================================================

def _compute_expected_by(refund: Refund) -> dt.datetime:
    """
    expected_by = initiated_at + workspace.sla_days
    """
    sla_days = getattr(getattr(refund, "workspace", None), "sla_days", None) or 7
    if not refund.initiated_at:
        refund.initiated_at = timezone.now()
    return refund.initiated_at + dt.timedelta(days=int(sla_days))


def _compute_risk_state(refund: Refund) -> str:
    """
    Deterministic risk model:
    - OVERDUE: now > expected_by
    - AT_RISK: due in <= 24h
    - DUE_SOON: due in <= 72h
    - SAFE otherwise
    """
    now = timezone.now()
    expected_by = refund.expected_by or _compute_expected_by(refund)
    delta = expected_by - now

    if now > expected_by:
        return Refund.RISK_OVERDUE
    if delta <= dt.timedelta(hours=24):
        return Refund.RISK_AT_RISK
    if delta <= dt.timedelta(hours=72):
        return Refund.RISK_DUE_SOON
    return Refund.RISK_SAFE


def _create_alert_for_refund(refund: Refund, new_state: str) -> None:
    """
    Create alert rows for non-SAFE risk states.
    Safe to call even if alerts app is missing.
    """
    try:
        from apps.alerts.models import Alert
    except Exception:
        return

    # Map risk state -> Alert fields
    if new_state == Refund.RISK_OVERDUE:
        alert_type = getattr(Alert, "TYPE_REFUND_OVERDUE", "refund_overdue")
        severity = getattr(Alert, "SEVERITY_DANGER", "danger")
        msg = f"Refund overdue: {refund.external_id}"
    elif new_state == Refund.RISK_AT_RISK:
        alert_type = getattr(Alert, "TYPE_REFUND_AT_RISK", "refund_at_risk")
        severity = getattr(Alert, "SEVERITY_WARNING", "warning")
        msg = f"Refund at risk: {refund.external_id}"
    elif new_state == Refund.RISK_DUE_SOON:
        alert_type = getattr(Alert, "TYPE_REFUND_DUE_SOON", "refund_due_soon")
        severity = getattr(Alert, "SEVERITY_WARNING", "warning")
        msg = f"Refund due soon: {refund.external_id}"
    else:
        return

    # Avoid spamming duplicates (same refund + same type still unread)
    try:
        exists = Alert.objects.filter(
            workspace=refund.workspace,
            type=alert_type,
            entity_type="refund",
            entity_id=refund.id,
            is_read=False,
        ).exists()
        if exists:
            return

        Alert.objects.create(
            workspace=refund.workspace,
            type=alert_type,
            severity=severity,
            entity_type="refund",
            entity_id=refund.id,
            message=msg,
        )
    except Exception:
        # never break sync
        return


def _apply_risk_and_alerts(refund: Refund) -> None:
    """
    Ensure expected_by + risk_state are consistent and alert is created when non-SAFE.
    """
    old_state = refund.risk_state

    refund.expected_by = _compute_expected_by(refund)
    refund.risk_state = _compute_risk_state(refund)
    refund.last_provider_update_at = timezone.now()
    refund.save(update_fields=["expected_by", "risk_state", "last_provider_update_at"])

    if refund.risk_state != Refund.RISK_SAFE and refund.risk_state != old_state:
        _create_alert_for_refund(refund, refund.risk_state)


# =========================================================
# Demo shift helper (this is what creates mixed states)
# =========================================================

def _demo_time_shift(refund: Refund) -> None:
    """
    DEMO_MODE only:
    shift initiated_at backwards so we naturally get SAFE/DUE_SOON/AT_RISK/OVERDUE.

    With SLA=7 days:
      - days_ago 0–3  => SAFE
      - days_ago 4–6  => DUE_SOON / AT_RISK
      - days_ago 7+   => OVERDUE
    """
    if not getattr(settings, "DEMO_MODE", False):
        return

    refund.raw_payload = refund.raw_payload or {}

    # Bias toward "interesting" demo: more due soon/at risk/overdue
    days_ago = random.choices(
        population=[0, 1, 2, 3, 4, 5, 6, 7, 9, 12, 14],
        weights=[4, 4, 4, 5, 10, 12, 12, 10, 10, 9, 8],
    )[0]

    refund.initiated_at = timezone.now() - dt.timedelta(days=days_ago)
    refund.expected_by = _compute_expected_by(refund)
    refund.last_provider_update_at = timezone.now()

    refund.save(update_fields=["initiated_at", "expected_by", "last_provider_update_at", "raw_payload"])


# =========================================================
# Stripe helpers
# =========================================================

def _stripe_key(conn: ProviderConnection) -> str:
    creds = conn.get_credentials()
    key = (creds or {}).get("secret_key")
    if not key:
        raise ValueError("Stripe secret key is missing. Save it in Connections first.")
    return key


def stripe_test_connection(conn: ProviderConnection) -> dict:
    stripe.api_key = _stripe_key(conn)
    return stripe.Account.retrieve()


def stripe_seed_demo_data(conn: ProviderConnection, *, count: int = 250) -> Tuple[int, int]:
    """
    Create demo PaymentIntents and some Refunds in Stripe TEST mode.
    """
    stripe.api_key = _stripe_key(conn)

    created = 0
    refunded = 0

    for i in range(count):
        amount = random.choice([1500, 2500, 5000, 7500, 12000, 19900])  # cents
        email = f"demo.customer{i % 50}@finops.local"

        pi = stripe.PaymentIntent.create(
            amount=amount,
            currency="usd",
            receipt_email=email,
            payment_method="pm_card_visa",
            confirm=True,
            off_session=True,
            description="FinOps demo seed",
            metadata={"finops_demo": "1"},
        )
        created += 1

        if random.random() < 0.35:  # slightly more refunds so dashboard has more signal
            stripe.Refund.create(payment_intent=pi["id"], metadata={"finops_demo": "1"})
            refunded += 1

    return created, refunded


def stripe_sync_last_days(conn: ProviderConnection, *, days: int = 30) -> dict:
    """
    Sync Charges + Refunds from Stripe into our DB.

    IMPORTANT:
    - Your Order.amount and Refund.amount are minor units (int).
    - Customer.external_id is required and unique per workspace -> use email as stable key.
    """
    stripe.api_key = _stripe_key(conn)
    since = int((timezone.now() - dt.timedelta(days=days)).timestamp())

    # ---------
    # Charges -> PaymentTransaction
    # ---------
    charges_iter = stripe.Charge.list(limit=100, created={"gte": since}).auto_paging_iter()

    txn_count = 0
    for ch in charges_iter:
        billing = ch.get("billing_details") or {}
        customer_email = billing.get("email") or ch.get("receipt_email") or "unknown@finops.local"

        customer, _ = Customer.objects.get_or_create(
            workspace=conn.workspace,
            external_id=customer_email,
            defaults={"email": customer_email, "name": customer_email.split("@")[0]},
        )

        # Order.external_id unique per workspace
        order, _ = Order.objects.get_or_create(
            workspace=conn.workspace,
            external_id=ch["id"],
            defaults={
                "provider": ProviderConnection.PROVIDER_STRIPE,
                "customer": customer,
                "amount": int(ch.get("amount") or 0),
                "currency": (ch.get("currency") or "usd").upper(),
                "status": "paid" if ch.get("paid") else "unpaid",
                "raw_payload": dict(ch),
            },
        )

        PaymentTransaction.objects.update_or_create(
            workspace=conn.workspace,
            external_id=ch["id"],
            defaults={
                "provider": ProviderConnection.PROVIDER_STRIPE,
                "order": order,
                "customer": customer,
                "amount": int(ch.get("amount") or 0),
                "currency": (ch.get("currency") or "usd").upper(),
                "status": "succeeded" if ch.get("paid") else "failed",
                "initiated_at": dt.datetime.fromtimestamp(
                    ch.get("created", int(timezone.now().timestamp())),
                    tz=dt.UTC,
                ),
                "updated_at": timezone.now(),
                "raw_payload": dict(ch),
            },
        )
        txn_count += 1

    # ---------
    # Refunds -> Refund model + risk/alerts
    # ---------
    refunds_iter = stripe.Refund.list(limit=100, created={"gte": since}).auto_paging_iter()

    refund_count = 0
    for r in refunds_iter:
        charge_id = r.get("charge")

        txn = None
        if charge_id:
            txn = PaymentTransaction.objects.filter(
                workspace=conn.workspace,
                external_id=charge_id,
            ).first()

        customer = txn.customer if txn else None
        order = txn.order if txn else None

        if not customer:
            customer, _ = Customer.objects.get_or_create(
                workspace=conn.workspace,
                external_id="unknown@finops.local",
                defaults={"email": "unknown@finops.local", "name": "Unknown"},
            )

        if not order:
            order, _ = Order.objects.get_or_create(
                workspace=conn.workspace,
                external_id=f"order_{r['id']}",
                defaults={
                    "provider": ProviderConnection.PROVIDER_STRIPE,
                    "customer": customer,
                    "amount": 0,
                    "currency": "USD",
                    "status": "unknown",
                    "raw_payload": {},
                },
            )

        if not txn:
            txn, _ = PaymentTransaction.objects.get_or_create(
                workspace=conn.workspace,
                external_id=f"txn_{r['id']}",
                defaults={
                    "provider": ProviderConnection.PROVIDER_STRIPE,
                    "order": order,
                    "customer": customer,
                    "amount": 0,
                    "currency": "USD",
                    "status": "unknown",
                    "raw_payload": {},
                },
            )

        refund, _ = Refund.objects.update_or_create(
            workspace=conn.workspace,
            external_id=r["id"],
            defaults={
                "provider": ProviderConnection.PROVIDER_STRIPE,
                "transaction": txn,
                "order": order,
                "customer": customer,
                "amount": int(r.get("amount") or 0),
                "currency": (r.get("currency") or "usd").upper(),
                "status": r.get("status") or "unknown",
                "initiated_at": dt.datetime.fromtimestamp(
                    r.get("created", int(timezone.now().timestamp())),
                    tz=dt.UTC,
                ),
                "raw_payload": dict(r),
                "last_provider_update_at": timezone.now(),
            },
        )

        # Demo shift + compute risk + create alerts
        _demo_time_shift(refund)
        _apply_risk_and_alerts(refund)

        refund_count += 1

    conn.last_sync_at = timezone.now()
    conn.status = ProviderConnection.STATUS_CONNECTED
    conn.save(update_fields=["last_sync_at", "status"])

    return {"transactions": txn_count, "refunds": refund_count}
