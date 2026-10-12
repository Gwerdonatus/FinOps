import hashlib
import hmac
import json
import time
from unittest.mock import Mock

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.ops_disputes.briefs import (
    BriefUnavailable,
    case_sources,
    generate_brief,
    source_hash,
    validate_draft,
)
from apps.ops_disputes.models import AIConfiguration, CaseBrief, Dispute, EvidenceFile, EvidenceItem
from apps.ops_disputes.uploads import save_evidence
from apps.ops_refunds.models import PaymentTransaction, Refund
from apps.providers.models import ProviderConnection, StripeWebhookEvent
from apps.providers.services import sync
from tests.test_phase2 import attach_membership, make_user, make_workspace

pytestmark = pytest.mark.django_db


@pytest.fixture
def case(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.ENCRYPTION_KEY = Fernet.generate_key().decode()
    settings.OPENAI_API_KEY = ""
    user = make_user()
    ws = make_workspace()
    attach_membership(user, ws)
    client.force_login(user)
    dispute = Dispute.objects.create(
        workspace=ws,
        external_id="du_case",
        amount=18000,
        currency="USD",
        status="needs_response",
        reason="product_not_received",
    )
    item = EvidenceItem.objects.create(dispute=dispute, type="delivery_proof")
    return dispute, item


@pytest.fixture
def connection(case):
    dispute, _ = case
    conn = ProviderConnection(
        workspace=dispute.workspace, provider="stripe", status="connected", account_id="acct_test"
    )
    conn.set_credentials({"secret_key": "sk_test_fixture", "webhook_secret": "whsec_fixture"})
    conn.save()
    return conn


def charge():
    return {
        "id": "ch_fixture",
        "livemode": False,
        "amount": 18000,
        "currency": "usd",
        "status": "succeeded",
        "paid": True,
        "created": 1700000000,
        "customer": "cus_fixture",
        "billing_details": {"email": "buyer@example.com"},
    }


def refund():
    return {
        "id": "re_fixture",
        "livemode": False,
        "charge": "ch_fixture",
        "amount": 18000,
        "currency": "usd",
        "status": "pending",
        "created": 1700000000,
    }


def dispute_record():
    return {
        "id": "du_fixture",
        "livemode": False,
        "charge": "ch_fixture",
        "amount": 18000,
        "currency": "usd",
        "status": "needs_response",
        "reason": "product_not_received",
        "created": 1700000000,
        "evidence_details": {"due_by": 1700200000},
    }


def test_upload_and_private_download(client, case):
    dispute, item = case
    url = reverse("ops_disputes:upload_evidence", args=[dispute.id, item.id])
    assert (
        client.post(
            url, {"file": SimpleUploadedFile("receipt.txt", b"Carrier record: tracking pending.")}
        ).status_code
        == 302
    )
    file = item.files.get()
    item.refresh_from_db()
    assert item.status == "uploaded"
    assert file.text_content == "Carrier record: tracking pending."
    assert file.sha256 == hashlib.sha256(file.text_content.encode()).hexdigest()
    download = reverse("ops_disputes:download_evidence", args=[file.id])
    response = client.get(download)
    assert response.status_code == 200
    assert b"".join(response.streaming_content) == file.text_content.encode()
    assert response["Cache-Control"] == "private, no-store"
    assert "attachment" in response["Content-Disposition"]
    client.logout()
    assert client.get(download).status_code == 302
    assert client.get("/media/" + file.file_path).status_code == 404


def test_evidence_is_workspace_scoped(client, case):
    _, item = case
    file = save_evidence(item, SimpleUploadedFile("note.txt", b"Evidence"))
    other = make_user(email="other@example.com")
    attach_membership(other, make_workspace(slug="other", name="Other"))
    client.force_login(other)
    assert client.get(reverse("ops_disputes:download_evidence", args=[file.id])).status_code == 404
    assert (
        client.post(
            reverse("ops_disputes:upload_evidence", args=[item.dispute_id, item.id]),
            {"file": SimpleUploadedFile("note.txt", b"New")},
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "name,data",
    [
        ("attack.html", b"<script>bad</script>"),
        ("fake.pdf", b"not a PDF"),
        ("bad.txt", b"\x00binary"),
        ("bad.txt", b"\xff"),
        ("empty.txt", b""),
    ],
)
def test_unsafe_uploads_rejected(case, name, data):
    with pytest.raises(ValidationError):
        save_evidence(case[1], SimpleUploadedFile(name, data))
    assert not EvidenceFile.objects.exists()


def test_upload_limits_and_traversal_download(client, case):
    item = case[1]
    with pytest.raises(ValidationError):
        save_evidence(item, SimpleUploadedFile("large.txt", b"x" * (5 * 1024 * 1024 + 1)))
    file = EvidenceFile.objects.create(item=item, file_path="../../.env", filename="secret")
    assert client.get(reverse("ops_disputes:download_evidence", args=[file.id])).status_code == 404


def test_case_sources_do_not_infer_document_contents(case):
    dispute, item = case
    save_evidence(item, SimpleUploadedFile("proof.pdf", b"%PDF-1.4\nfixture"))
    sources = case_sources(dispute)
    assert "180.00 USD" in sources[0]["text"]
    assert "do not infer" in sources[-1]["text"]
    assert "file_" in sources[-1]["id"]


def test_ai_unconfigured_and_consent_required(client, case, monkeypatch):
    dispute = case[0]
    with pytest.raises(BriefUnavailable, match="not configured"):
        generate_brief(dispute)
    posted = Mock()
    monkeypatch.setattr("apps.ops_disputes.briefs.requests.post", posted)
    assert client.post(reverse("ops_disputes:create_brief", args=[dispute.id])).status_code == 302
    posted.assert_not_called()
    assert (
        b"source-based brief"
        in client.get(reverse("ops_disputes:detail", args=[dispute.id])).content
    )


def draft_for(sources):
    return {
        "observations": [
            {
                "text": "The case requires investigation.",
                "source_id": sources[0]["id"],
                "quote": sources[0]["text"],
            }
        ],
        "next_steps": [],
    }


def test_ai_draft_is_structured_grounded_and_cached(case, settings, monkeypatch):
    dispute = case[0]
    settings.OPENAI_API_KEY = "sk-fixture"
    sources = case_sources(dispute)
    payload = draft_for(sources)
    response = Mock()
    response.json.return_value = {
        "status": "completed",
        "output": [
            {"type": "message", "content": [{"type": "output_text", "text": json.dumps(payload)}]}
        ],
    }
    post = Mock(return_value=response)
    monkeypatch.setattr("apps.ops_disputes.briefs.requests.post", post)
    brief = generate_brief(dispute)
    assert brief.payload == payload
    assert brief.source_hash == source_hash(sources)
    assert generate_brief(dispute).id == brief.id
    assert post.call_count == 1
    assert post.call_args.kwargs["json"]["store"] is False
    assert post.call_args.kwargs["json"]["text"]["format"]["strict"] is True
    assert "UNTRUSTED" in post.call_args.kwargs["json"]["instructions"]
    assert "tools" not in post.call_args.kwargs["json"]


def test_invalid_citations_and_refusals_fail_closed(case, settings, monkeypatch):
    settings.OPENAI_API_KEY = "sk-fixture"
    sources = case_sources(case[0])
    payload = draft_for(sources)
    payload["observations"][0]["quote"] = "Invented proof of delivery"
    with pytest.raises(BriefUnavailable):
        validate_draft(payload, sources)
    response = Mock()
    response.json.return_value = {
        "status": "completed",
        "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "No"}]}],
    }
    monkeypatch.setattr("apps.ops_disputes.briefs.requests.post", Mock(return_value=response))
    with pytest.raises(BriefUnavailable):
        generate_brief(case[0])
    assert not CaseBrief.objects.exists()


def test_changed_sources_mark_brief_stale(client, case):
    dispute, item = case
    sources = case_sources(dispute)
    CaseBrief.objects.create(
        dispute=dispute,
        source_hash=source_hash(sources),
        sources=sources,
        model="fixture",
        payload=draft_for(sources),
    )
    item.notes = "Changed review"
    item.save()
    response = client.get(reverse("ops_disputes:detail", args=[dispute.id]))
    assert b"out of date" in response.content


def test_ai_configuration_is_encrypted_and_admin_only(client, case):
    key = "sk-fixture-long-enough-for-test"
    client.post(reverse("providers:configure_ai"), {"api_key": key})
    config = AIConfiguration.objects.get()
    assert key not in config.credentials_encrypted
    from apps.workspaces.models import Membership

    Membership.objects.update(role="agent")
    client.post(reverse("providers:configure_ai"), {"api_key": "sk-another-fixture-long-enough"})
    config.refresh_from_db()
    from apps.providers.services.crypto import decrypt_json

    assert decrypt_json(config.credentials_encrypted)["api_key"] == key


def test_stripe_sync_preserves_dates_and_is_repeatable(connection, settings, monkeypatch):
    settings.DEMO_MODE = True
    monkeypatch.setattr(sync.stripe.Charge, "retrieve", Mock(return_value=charge()))
    for resource, obj in [
        (sync.stripe.Charge, charge()),
        (sync.stripe.Refund, refund()),
        (sync.stripe.Dispute, dispute_record()),
    ]:
        page = Mock()
        page.auto_paging_iter.return_value = [obj]
        monkeypatch.setattr(resource, "list", Mock(return_value=page))
    Dispute.objects.filter(external_id="du_case").delete()
    first = sync.stripe_sync_last_days(connection)
    second = sync.stripe_sync_last_days(connection)
    assert first == second == {"transactions": 1, "refunds": 1, "disputes": 1}
    assert PaymentTransaction.objects.count() == 1
    assert Refund.objects.get().initiated_at.timestamp() == 1700000000
    assert Dispute.objects.get(external_id="du_fixture").deadline_at.timestamp() == 1700200000
    assert EvidenceItem.objects.filter(dispute__external_id="du_fixture").count() == 4
    connection.refresh_from_db()
    assert connection.last_sync_at and not connection.sync_error


def test_stripe_rejects_live_key_and_records(connection):
    connection.set_credentials({"secret_key": "sk_live_fixture"})
    with pytest.raises(ValueError, match="sandbox"):
        sync.stripe_test_connection(connection)
    with pytest.raises(ValueError, match="sandbox"):
        sync.import_charge(connection, {**charge(), "livemode": True})


def test_stripe_failure_keeps_last_success_and_rolls_back(connection, monkeypatch):
    from django.utils import timezone

    connection.last_sync_at = timezone.now()
    connection.save()
    previous = connection.last_sync_at
    monkeypatch.setattr(
        sync.stripe.Charge, "list", Mock(side_effect=RuntimeError("sensitive error"))
    )
    with pytest.raises(RuntimeError):
        sync.stripe_sync_last_days(connection)
    connection.refresh_from_db()
    assert connection.last_sync_at == previous
    assert connection.sync_error and "sensitive" not in connection.sync_error
    assert not PaymentTransaction.objects.exists()


def signed_event(event):
    body = json.dumps(event).encode()
    stamp = str(int(time.time()))
    signature = hmac.new(b"whsec_fixture", stamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return body, f"t={stamp},v1={signature}"


def test_signed_webhooks_deduplicate_and_reject_live(client, connection, monkeypatch):
    event = {
        "id": "evt_fixture",
        "type": "refund.updated",
        "livemode": False,
        "data": {"object": {"id": "re_fixture"}},
    }
    body, signature = signed_event(event)
    refresh = Mock()
    monkeypatch.setattr("apps.providers.webhooks.refresh_event", refresh)
    url = reverse("stripe_webhook", args=[connection.id])
    for _ in range(2):
        assert (
            client.post(
                url, body, content_type="application/json", HTTP_STRIPE_SIGNATURE=signature
            ).status_code
            == 200
        )
    assert refresh.call_count == 1
    assert StripeWebhookEvent.objects.count() == 1
    assert (
        client.post(
            url, body, content_type="application/json", HTTP_STRIPE_SIGNATURE="bad"
        ).status_code
        == 400
    )
    body, signature = signed_event({**event, "livemode": True})
    assert (
        client.post(
            url, body, content_type="application/json", HTTP_STRIPE_SIGNATURE=signature
        ).status_code
        == 400
    )


def test_failed_webhook_can_retry(client, connection, monkeypatch):
    body, signature = signed_event(
        {
            "id": "evt_retry",
            "type": "refund.updated",
            "livemode": False,
            "data": {"object": {"id": "re_fixture"}},
        }
    )
    refresh = Mock(side_effect=RuntimeError("temporary"))
    monkeypatch.setattr("apps.providers.webhooks.refresh_event", refresh)
    url = reverse("stripe_webhook", args=[connection.id])
    assert (
        client.post(
            url, body, content_type="application/json", HTTP_STRIPE_SIGNATURE=signature
        ).status_code
        == 503
    )
    assert not StripeWebhookEvent.objects.exists()
    refresh.side_effect = None
    assert (
        client.post(
            url, body, content_type="application/json", HTTP_STRIPE_SIGNATURE=signature
        ).status_code
        == 200
    )


def test_webhook_fetches_current_provider_state(connection, monkeypatch):
    retrieve = Mock(return_value=refund())
    monkeypatch.setattr(sync.stripe.Refund, "retrieve", retrieve)
    monkeypatch.setattr(sync.stripe.Charge, "retrieve", Mock(return_value=charge()))
    sync.refresh_event(
        connection,
        {"type": "refund.updated", "data": {"object": {"id": "re_fixture", "status": "obsolete"}}},
    )
    assert Refund.objects.get().status == "pending"
    assert retrieve.call_args.kwargs["api_key"] == "sk_test_fixture"


def test_upload_metadata_failure_leaves_no_orphan(case, monkeypatch, settings):
    from pathlib import Path

    item = case[1]
    monkeypatch.setattr(item, "save", Mock(side_effect=RuntimeError("database failure")))
    with pytest.raises(RuntimeError):
        save_evidence(item, SimpleUploadedFile("note.txt", b"Private evidence"))
    assert not EvidenceFile.objects.exists()
    assert not list(Path(settings.MEDIA_ROOT).rglob("*.txt"))


def test_unreadable_ai_credentials_do_not_break_case(client, case):
    dispute = case[0]
    AIConfiguration.objects.create(
        workspace=dispute.workspace, credentials_encrypted="invalid-ciphertext"
    )
    response = client.get(reverse("ops_disputes:detail", args=[dispute.id]))
    assert response.status_code == 200
    assert b"credentials are unavailable" in response.content
