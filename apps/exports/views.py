from __future__ import annotations

from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.exports.models import ExportPack
from apps.exports.services import create_dispute_evidence_pack_pdf, create_overdue_refunds_csv, create_overdue_refunds_pdf
from apps.ops_disputes.models import Dispute


@login_required
def exports_list(request: HttpRequest) -> HttpResponse:
    ws = request.workspace
    exports = ExportPack.objects.filter(workspace=ws).order_by("-created_at")[:200]
    return render(request, "exports/list.html", {"exports": exports})


@login_required
def export_overdue_refunds_pdf(request: HttpRequest) -> HttpResponse:
    ws = request.workspace
    create_overdue_refunds_pdf(ws.id)
    messages.success(request, "Overdue refunds PDF generated.")
    return redirect("exports:list")


@login_required
def export_overdue_refunds_csv(request: HttpRequest) -> HttpResponse:
    ws = request.workspace
    create_overdue_refunds_csv(ws.id)
    messages.success(request, "Overdue refunds CSV generated.")
    return redirect("exports:list")


@login_required
def export_dispute_evidence_pack(request: HttpRequest, dispute_id: int) -> HttpResponse:
    ws = request.workspace
    dispute = get_object_or_404(Dispute, id=dispute_id, workspace=ws)
    create_dispute_evidence_pack_pdf(dispute.id)
    messages.success(request, f"Evidence pack generated for dispute {dispute.external_id}.")
    return redirect("ops_disputes:detail", dispute_id=dispute.id)


@login_required
def export_download(request: HttpRequest, export_id: int) -> HttpResponse:
    ws = request.workspace
    export = get_object_or_404(ExportPack, id=export_id, workspace=ws)

    if export.status != ExportPack.STATUS_READY or not export.file_path:
        raise Http404("Export not ready")

    p = Path(export.file_path)
    if not p.exists():
        raise Http404("Export file missing")

    # Let browser download with a safe filename
    filename = p.name
    return FileResponse(open(p, "rb"), as_attachment=True, filename=filename)
