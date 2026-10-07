from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.exports.models import ExportPack
from apps.ops_disputes.models import Dispute
from apps.ops_refunds.models import Customer, Order, PaymentTransaction, Refund
from apps.workspaces.models import Membership, Workspace

pytestmark = pytest.mark.django_db


def make_user(email="user@example.com", password="pass1234"):
    User = get_user_model()
    return User.objects.create_user(username=email, email=email, password=password)


def make_workspace(name="WS", slug="ws", sla_days=7):
    return Workspace.objects.create(name=name, slug=slug, sla_days=sla_days)


def attach_membership(user, workspace, role="admin"):
    return Membership.objects.create(user=user, workspace=workspace, role=role)


def seed_overdue_refund(workspace):
    cust = Customer.objects.create(
        workspace=workspace, external_id="cus_overdue", email="buyer@ex.com", name="Buyer"
    )
    order = Order.objects.create(
        workspace=workspace, external_id="ord_overdue", customer=cust, amount=1000, currency="NGN"
    )
    txn = PaymentTransaction.objects.create(
        workspace=workspace,
        external_id="txn_overdue",
        customer=cust,
        order=order,
        amount=1000,
        currency="NGN",
    )
    return Refund.objects.create(
        workspace=workspace,
        external_id="ref_overdue",
        provider="stripe",
        transaction=txn,
        order=order,
        customer=cust,
        amount=1000,
        currency="NGN",
        initiated_at=timezone.now(),
        expected_by=timezone.now(),
        status="pending",
        risk_state=Refund.RISK_OVERDUE,
    )


def seed_dispute(workspace):
    cust = Customer.objects.create(
        workspace=workspace, external_id="cus_d", email="d@e.com", name="D"
    )
    order = Order.objects.create(
        workspace=workspace, external_id="ord_d", customer=cust, amount=2000, currency="NGN"
    )
    txn = PaymentTransaction.objects.create(
        workspace=workspace,
        external_id="txn_d",
        customer=cust,
        order=order,
        amount=2000,
        currency="NGN",
    )
    dispute = Dispute.objects.create(
        workspace=workspace,
        provider="stripe",
        external_id="dp_1",
        transaction=txn,
        order=order,
        customer=cust,
        amount=2000,
        currency="NGN",
        status="needs_response",
        reason="fraud",
    )
    # checklist
    dispute.evidence_items.create(type="policy", status="missing")
    dispute.evidence_items.create(type="customer_comms", status="missing")
    return dispute


@override_settings(MEDIA_ROOT=Path("test_media"))
def test_generate_overdue_refunds_pdf(client, settings):
    user = make_user()
    ws = make_workspace()
    attach_membership(user, ws)
    seed_overdue_refund(ws)

    client.login(username=user.username, password="pass1234")
    assert client.get(reverse("exports:refunds_overdue_pdf")).status_code == 405

    resp = client.post(reverse("exports:refunds_overdue_pdf"))
    assert resp.status_code == 302

    exp = ExportPack.objects.filter(workspace=ws, type="refund_overdue_report_pdf").latest(
        "created_at"
    )
    assert exp.status == "ready"
    assert exp.file_path
    p = Path(exp.file_path)
    assert p.exists()
    assert p.stat().st_size > 0


@override_settings(MEDIA_ROOT=Path("test_media"))
def test_generate_dispute_evidence_pack_pdf(client):
    user = make_user(email="u2@example.com")
    ws = make_workspace(name="WS2", slug="ws2")
    attach_membership(user, ws)

    dispute = seed_dispute(ws)

    client.login(username=user.username, password="pass1234")
    url = reverse("exports:dispute_evidence_pack", kwargs={"dispute_id": dispute.id})
    assert client.get(url).status_code == 405

    resp = client.post(url)
    assert resp.status_code == 302

    exp = ExportPack.objects.filter(workspace=ws, type="evidence_pack_pdf").latest("created_at")
    p = Path(exp.file_path)
    assert p.exists()
    assert p.stat().st_size > 0
