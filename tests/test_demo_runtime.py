import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.alerts.models import Alert
from apps.exports.services import _safe_filename
from apps.ops_disputes.models import Dispute, EvidenceItem
from apps.ops_refunds.models import Refund
from apps.ops_refunds.services.risk import apply_risk
from apps.ops_refunds.templatetags.money import format_money
from tests.test_phase2 import attach_membership, make_user, make_workspace, seed_refund


@pytest.mark.django_db
def test_synthetic_seed_is_repeatable(settings):
    settings.DEMO_MODE = True
    call_command("seed_demo")
    counts = (
        Refund.objects.count(),
        Dispute.objects.count(),
        EvidenceItem.objects.count(),
        Alert.objects.count(),
    )
    assert counts == (4, 1, 4, 3)
    assert set(Refund.objects.values_list("risk_state", flat=True)) == {
        "SAFE",
        "DUE_SOON",
        "AT_RISK",
        "OVERDUE",
    }
    call_command("seed_demo")
    assert counts == (
        Refund.objects.count(),
        Dispute.objects.count(),
        EvidenceItem.objects.count(),
        Alert.objects.count(),
    )


@pytest.mark.django_db
def test_completed_refund_is_not_overdue():
    from datetime import timedelta

    from django.utils import timezone

    workspace = make_workspace()
    refund = seed_refund(workspace, initiated_at=timezone.now() - timedelta(days=10))
    refund.status = "succeeded"
    refund.save()
    apply_risk(refund, 7)
    assert refund.risk_state == "SAFE"
    assert not Alert.objects.exists()


@pytest.mark.django_db
def test_risk_mutation_requires_post(client):
    user = make_user()
    workspace = make_workspace()
    attach_membership(user, workspace)
    client.force_login(user)
    assert client.get(reverse("ops_refunds:recalc")).status_code == 405


def test_export_names_do_not_collide():
    assert _safe_filename("report", "pdf") != _safe_filename("report", "pdf")


def test_currency_display_uses_minor_units():
    assert format_money(4500, "USD") == "45.00 USD"
    assert format_money(4500, "JPY") == "4,500 JPY"
    assert "minor units" in format_money(4500, "XXX")


@pytest.mark.django_db
def test_evidence_review_is_scoped_and_post_only(client):
    user = make_user()
    workspace = make_workspace()
    attach_membership(user, workspace)
    dispute = Dispute.objects.create(workspace=workspace, external_id="case_review")
    item = EvidenceItem.objects.create(dispute=dispute, type="policy")
    client.force_login(user)
    url = reverse("ops_disputes:update_evidence", args=[dispute.id, item.id])
    assert client.get(url).status_code == 405
    assert client.post(url, {"status": "reviewed", "notes": "Policy verified."}).status_code == 302
    item.refresh_from_db()
    assert item.status == "reviewed"
    assert item.notes == "Policy verified."
    other = make_workspace(name="Other", slug="other")
    foreign = Dispute.objects.create(workspace=other, external_id="foreign_case")
    foreign_item = EvidenceItem.objects.create(dispute=foreign, type="policy")
    foreign_url = reverse("ops_disputes:update_evidence", args=[foreign.id, foreign_item.id])
    assert client.post(foreign_url, {"status": "reviewed"}).status_code == 404
    assert client.post(url, {"status": "uploaded"}).status_code == 302
    item.refresh_from_db()
    assert item.status == "reviewed"


@pytest.mark.django_db
def test_sla_change_updates_cached_deadline_without_duplicate_alert():
    from datetime import timedelta

    from django.utils import timezone

    workspace = make_workspace()
    refund = seed_refund(workspace, initiated_at=timezone.now() - timedelta(days=5))
    apply_risk(refund, 7)
    initial = refund.expected_by
    assert Alert.objects.count() == 1
    apply_risk(refund, 7)
    assert Alert.objects.count() == 1
    apply_risk(refund, 10)
    assert refund.expected_by == initial + timedelta(days=3)
    assert refund.risk_state == "SAFE"
    assert Alert.objects.filter(resolved_at__isnull=False).count() == 1


@pytest.mark.django_db
def test_exports_page_has_visible_generation_controls(client):
    user = make_user()
    workspace = make_workspace()
    attach_membership(user, workspace)
    client.force_login(user)
    response = client.get(reverse("exports:list"))
    assert response.status_code == 200
    assert b"Export Overdue Refunds (PDF)" in response.content
    assert b"Export history" in response.content


@pytest.mark.django_db
def test_alert_links_open_the_refund_not_an_unmatched_search(client):
    from datetime import timedelta

    from django.utils import timezone

    user = make_user()
    workspace = make_workspace()
    attach_membership(user, workspace)
    refund = seed_refund(workspace, initiated_at=timezone.now() - timedelta(days=10))
    apply_risk(refund, workspace.sla_days)
    client.force_login(user)
    response = client.get(reverse("alerts:list"))
    assert reverse("ops_refunds:detail", args=[refund.id]).encode() in response.content
