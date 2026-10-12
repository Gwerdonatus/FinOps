from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Dispute, EvidenceItem

DEFAULT_CHECKLIST = ["policy", "customer_comms", "delivery_proof", "refund_proof"]


@login_required
def dispute_list(request: HttpRequest) -> HttpResponse:
    ws = request.workspace
    disputes = (
        Dispute.objects.filter(workspace=ws)
        .select_related("customer", "order", "transaction")
        .order_by("-created_at")[:200]
    )
    return render(request, "disputes/list.html", {"disputes": disputes})


@login_required
def dispute_detail(request: HttpRequest, dispute_id: int) -> HttpResponse:
    ws = request.workspace
    dispute = get_object_or_404(
        Dispute.objects.select_related("customer", "order", "transaction").prefetch_related(
            "evidence_items", "evidence_items__files"
        ),
        workspace=ws,
        id=dispute_id,
    )

    # Ensure minimal checklist exists (idempotent)
    existing = set(dispute.evidence_items.values_list("type", flat=True))
    to_create = [t for t in DEFAULT_CHECKLIST if t not in existing]
    for t in to_create:
        dispute.evidence_items.create(type=t, status="missing")

    evidence_items = dispute.evidence_items.all().order_by("type")
    return render(
        request,
        "disputes/detail.html",
        {"dispute": dispute, "evidence_items": evidence_items},
    )


@login_required
@require_POST
def update_evidence(request, dispute_id, item_id):
    item = get_object_or_404(
        EvidenceItem, id=item_id, dispute_id=dispute_id, dispute__workspace=request.workspace
    )
    status = request.POST.get("status", "")
    notes = request.POST.get("notes", "").strip()
    if status not in {"missing", "reviewed", "not_applicable"} or len(notes) > 4000:
        messages.error(
            request, "Choose a valid checklist status and keep notes within 4,000 characters."
        )
        return redirect("ops_disputes:detail", dispute_id=dispute_id)
    item.status = status
    item.notes = notes
    item.save(update_fields=["status", "notes"])
    messages.success(request, "Evidence checklist updated. No provider submission was made.")
    return redirect("ops_disputes:detail", dispute_id=dispute_id)
