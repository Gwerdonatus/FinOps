from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.alerts.models import Alert
from apps.ops_refunds.models import Customer, Order, PaymentTransaction, Refund
from apps.ops_refunds.services.risk import apply_risk, apply_risk_for_workspace
from apps.workspaces.models import Membership, Workspace

pytestmark = pytest.mark.django_db


def make_user(email="user@example.com", password="pass1234"):
    User = get_user_model()
    user = User.objects.create_user(username=email, email=email, password=password)
    return user


def make_workspace(name="WS One", slug="ws-one", sla_days=7):
    return Workspace.objects.create(name=name, slug=slug, sla_days=sla_days)


def attach_membership(user, workspace, role="admin"):
    return Membership.objects.create(user=user, workspace=workspace, role=role)


def seed_refund(workspace, initiated_at=None, external_id="ref_1"):
    cust = Customer.objects.create(
        workspace=workspace, external_id="cus_1", email="c@e.com", name="C"
    )
    order = Order.objects.create(
        workspace=workspace, external_id="ord_1", customer=cust, amount=1000, currency="NGN"
    )
    txn = PaymentTransaction.objects.create(
        workspace=workspace,
        external_id="txn_1",
        customer=cust,
        order=order,
        amount=1000,
        currency="NGN",
    )
    return Refund.objects.create(
        workspace=workspace,
        external_id=external_id,
        provider="stripe",
        transaction=txn,
        order=order,
        customer=cust,
        amount=1000,
        currency="NGN",
        initiated_at=initiated_at or timezone.now(),
        status="pending",
    )


def test_workspace_created():
    ws = make_workspace()
    assert ws.slug == "ws-one"
    assert ws.sla_days == 7


def test_membership_roles():
    user = make_user()
    ws = make_workspace()
    m = attach_membership(user, ws, role=Membership.ROLE_AGENT)
    assert m.role == "agent"


def test_login_required_redirects(client):
    resp = client.get(reverse("dashboard"))
    assert resp.status_code in (301, 302)
    assert reverse("login") in resp.url


def test_homepage_200_after_login(client):
    user = make_user()
    ws = make_workspace()
    attach_membership(user, ws)
    client.login(username=user.username, password="pass1234")

    resp = client.get(reverse("dashboard"))
    assert resp.status_code == 200
    assert b"Dashboard" in resp.content


def test_workspace_scoping_blocks_cross_access(client):
    user = make_user()
    ws1 = make_workspace(name="WS1", slug="ws1")
    ws2 = make_workspace(name="WS2", slug="ws2")
    attach_membership(user, ws1)

    refund_ws2 = seed_refund(ws2, external_id="ref_ws2")
    client.login(username=user.username, password="pass1234")

    resp = client.get(reverse("ops_refunds:detail", kwargs={"refund_id": refund_ws2.id}))
    assert resp.status_code == 404


def test_nav_pages_200(client):
    user = make_user()
    ws = make_workspace()
    attach_membership(user, ws)
    client.login(username=user.username, password="pass1234")

    urls = [
        reverse("dashboard"),
        reverse("ops_refunds:list"),
        reverse("ops_search:search"),
        reverse("ops_disputes:list"),
        reverse("exports:list"),
        reverse("alerts:list"),
        reverse("providers:connections"),
    ]
    for u in urls:
        resp = client.get(u)
        assert resp.status_code == 200


def test_refund_risk_transition_creates_alert():
    ws = make_workspace(sla_days=7)
    refund = seed_refund(
        ws, initiated_at=timezone.now() - timedelta(days=10), external_id="ref_overdue_test"
    )

    old_state, new_state = apply_risk(refund, ws.sla_days)
    assert new_state in ("OVERDUE", "AT_RISK", "DUE_SOON", "SAFE")

    # For this setup it should be overdue
    assert Refund.objects.get(id=refund.id).risk_state == "OVERDUE"
    assert Alert.objects.filter(workspace=ws, type=Alert.TYPE_REFUND_OVERDUE).exists()


def test_apply_risk_for_workspace_updates_only_changed_refunds():
    ws = make_workspace(sla_days=7)
    overdue = seed_refund(
        ws,
        initiated_at=timezone.now() - timedelta(days=10),
        external_id="ref_workspace_overdue",
    )

    updated = apply_risk_for_workspace(ws.id)

    overdue.refresh_from_db()
    assert updated == 1
    assert overdue.risk_state == Refund.RISK_OVERDUE
    assert overdue.expected_by is not None

    assert apply_risk_for_workspace(ws.id) == 0
    assert (
        Alert.objects.filter(
            workspace=ws,
            type=Alert.TYPE_REFUND_OVERDUE,
            entity_id=overdue.id,
        ).count()
        == 1
    )


def test_mark_all_read_endpoint(client):
    user = make_user()
    ws = make_workspace()
    attach_membership(user, ws)
    client.login(username=user.username, password="pass1234")

    # create an alert
    Alert.objects.create(
        workspace=ws,
        type=Alert.TYPE_REFUND_DUE_SOON,
        severity=Alert.SEVERITY_WARNING,
        entity_type="refund",
        entity_id=1,
        message="Test alert",
    )
    assert Alert.objects.filter(workspace=ws, is_read=False).count() == 1

    assert client.get(reverse("alerts:mark_all_read")).status_code == 405

    resp = client.post(reverse("alerts:mark_all_read"))
    assert resp.status_code in (301, 302)
    assert Alert.objects.filter(workspace=ws, is_read=False).count() == 0
