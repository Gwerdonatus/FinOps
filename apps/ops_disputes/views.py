from pathlib import PurePosixPath

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .briefs import (
    BriefUnavailable,
    ai_key,
    case_sources,
    display_draft,
    generate_brief,
    source_hash,
)
from .models import Dispute, EvidenceFile, EvidenceItem
from .uploads import save_evidence

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
    sources = case_sources(dispute)
    brief = dispute.briefs.order_by("-created_at").first()
    try:
        configured = bool(ai_key(dispute.workspace))
    except BriefUnavailable as exc:
        configured = False
        messages.warning(request, str(exc))
    return render(
        request,
        "disputes/detail.html",
        {
            "dispute": dispute,
            "evidence_items": evidence_items,
            "sources": sources,
            "ai_configured": configured,
            "brief": brief,
            "draft": display_draft(brief) if brief else None,
            "brief_stale": bool(brief and brief.source_hash != source_hash(sources)),
        },
    )


@login_required
@require_POST
def update_evidence(request, dispute_id, item_id):
    item = get_object_or_404(
        EvidenceItem, id=item_id, dispute_id=dispute_id, dispute__workspace=request.workspace
    )
    status = request.POST.get("status", "")
    notes = request.POST.get("notes", "").strip()
    valid_statuses = {"missing", "reviewed", "not_applicable"}
    if item.files.exists():
        valid_statuses.add("uploaded")
    if status not in valid_statuses or len(notes) > 4000:
        messages.error(
            request, "Choose a valid checklist status and keep notes within 4,000 characters."
        )
        return redirect("ops_disputes:detail", dispute_id=dispute_id)
    item.status = status
    item.notes = notes
    item.save(update_fields=["status", "notes"])
    messages.success(request, "Evidence checklist updated. No provider submission was made.")
    return redirect("ops_disputes:detail", dispute_id=dispute_id)


@login_required
@require_POST
def upload_evidence(request, dispute_id, item_id):
    item = get_object_or_404(
        EvidenceItem, id=item_id, dispute_id=dispute_id, dispute__workspace=request.workspace
    )
    upload = request.FILES.get("file")
    if not upload:
        messages.error(request, "Choose an evidence file.")
    else:
        try:
            save_evidence(item, upload)
            messages.success(
                request,
                "Evidence stored privately. Uploading does not verify its contents or submit it to Stripe.",
            )
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
    return redirect("ops_disputes:detail", dispute_id=dispute_id)


@login_required
def download_evidence(request, file_id):
    file = get_object_or_404(EvidenceFile, id=file_id, item__dispute__workspace=request.workspace)
    path = PurePosixPath(file.file_path)
    if (
        path.is_absolute()
        or ".." in path.parts
        or not file.file_path.startswith(f"evidence/{request.workspace.id}/")
    ):
        raise Http404
    try:
        response = FileResponse(
            default_storage.open(file.file_path, "rb"),
            as_attachment=True,
            filename=file.filename,
            content_type="application/octet-stream",
        )
    except FileNotFoundError as exc:
        raise Http404 from exc
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@require_POST
def create_brief(request, dispute_id):
    dispute = get_object_or_404(Dispute, id=dispute_id, workspace=request.workspace)
    if request.POST.get("consent") != "yes":
        messages.error(request, "Confirm that the case sources may be sent to OpenAI.")
    else:
        try:
            generate_brief(dispute)
            messages.success(
                request, "AI draft ready. Check every interpretation against the linked sources."
            )
        except BriefUnavailable as exc:
            messages.error(request, str(exc))
    return redirect("ops_disputes:detail", dispute_id=dispute_id)
