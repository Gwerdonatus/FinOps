"""Repeatable local operations scenario; never calls a payment provider."""

from datetime import timedelta

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.ops_disputes.models import Dispute, EvidenceItem
from apps.ops_refunds.models import Customer, Order, PaymentTransaction, Refund
from apps.ops_refunds.services.risk import apply_risk
from apps.workspaces.models import Workspace


class Command(BaseCommand):
    help = "Seed labelled synthetic refunds, alerts and dispute context (DEMO_MODE only)."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEMO_MODE:
            raise CommandError("Set DEMO_MODE=1 for the local demo.")
        call_command("seed_dev")
        workspace = Workspace.objects.get(slug="demo-store")
        now = timezone.now()
        for index, days_left in enumerate((5, 2, 0.5, -2), start=1):
            customer, _ = Customer.objects.get_or_create(
                workspace=workspace,
                external_id=f"demo_customer_{index}",
                defaults={
                    "email": f"buyer{index}@example.com",
                    "name": f"Demo Buyer {index}",
                    "raw_payload": {"synthetic": True},
                },
            )
            order, _ = Order.objects.get_or_create(
                workspace=workspace,
                external_id=f"demo_order_{index}",
                defaults={
                    "customer": customer,
                    "amount": index * 4500,
                    "currency": "USD",
                    "provider": "demo",
                    "status": "fulfilled",
                    "raw_payload": {"synthetic": True},
                },
            )
            payment, _ = PaymentTransaction.objects.get_or_create(
                workspace=workspace,
                external_id=f"demo_payment_{index}",
                defaults={
                    "customer": customer,
                    "order": order,
                    "amount": order.amount,
                    "currency": "USD",
                    "provider": "demo",
                    "status": "succeeded",
                    "raw_payload": {"synthetic": True},
                },
            )
            refund, _ = Refund.objects.get_or_create(
                workspace=workspace,
                external_id=f"demo_refund_{index}",
                defaults={
                    "customer": customer,
                    "order": order,
                    "transaction": payment,
                    "amount": order.amount,
                    "currency": "USD",
                    "provider": "demo",
                    "status": "pending",
                    "initiated_at": now - timedelta(days=workspace.sla_days - days_left),
                    "raw_payload": {"synthetic": True},
                },
            )
            apply_risk(refund, workspace.sla_days)
        dispute, _ = Dispute.objects.get_or_create(
            workspace=workspace,
            external_id="demo_dispute_1",
            defaults={
                "customer": customer,
                "order": order,
                "transaction": payment,
                "amount": order.amount,
                "currency": "USD",
                "provider": "demo",
                "status": "needs_response",
                "reason": "product_not_received",
                "deadline_at": now + timedelta(days=3),
                "raw_payload": {"synthetic": True},
            },
        )
        for evidence_type in ("policy", "customer_comms", "delivery_proof", "refund_proof"):
            EvidenceItem.objects.get_or_create(dispute=dispute, type=evidence_type)
        self.stdout.write(
            self.style.SUCCESS(
                "Synthetic demo ready: 4 refunds, 1 dispute. Existing records preserved."
            )
        )
