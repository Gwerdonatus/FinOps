from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from .models import Dispute

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
