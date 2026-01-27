from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from django.conf import settings
from django.utils import timezone

from apps.exports.models import ExportPack
from apps.ops_disputes.models import Dispute
from apps.ops_refunds.models import Refund
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


@dataclass(frozen=True)
class ExportResult:
    export: ExportPack
    abs_path: Path


def _exports_dir() -> Path:
    d = Path(settings.MEDIA_ROOT) / "exports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_filename(prefix: str, ext: str) -> str:
    ts = timezone.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}.{ext}"


def create_overdue_refunds_pdf(workspace_id: int) -> ExportResult:
    qs = (
        Refund.objects.filter(workspace_id=workspace_id, risk_state=Refund.RISK_OVERDUE)
        .select_related("customer", "order", "transaction")
        .order_by("-initiated_at")
    )
    filename = _safe_filename("overdue_refunds", "pdf")
    abs_path = _exports_dir() / filename

    export = ExportPack.objects.create(
        workspace_id=workspace_id,
        type="refund_overdue_report_pdf",
        status=ExportPack.STATUS_READY,
        file_path=str(abs_path),
    )

    _render_overdue_refunds_pdf(abs_path, qs)
    return ExportResult(export=export, abs_path=abs_path)


def create_overdue_refunds_csv(workspace_id: int) -> ExportResult:
    qs = (
        Refund.objects.filter(workspace_id=workspace_id, risk_state=Refund.RISK_OVERDUE)
        .select_related("customer", "order", "transaction")
        .order_by("-initiated_at")
    )
    filename = _safe_filename("overdue_refunds", "csv")
    abs_path = _exports_dir() / filename

    export = ExportPack.objects.create(
        workspace_id=workspace_id,
        type="refund_overdue_report_csv",
        status=ExportPack.STATUS_READY,
        file_path=str(abs_path),
    )

    with abs_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "refund_external_id",
                "amount",
                "currency",
                "status",
                "risk_state",
                "initiated_at",
                "expected_by",
                "customer_email",
                "order_external_id",
                "transaction_external_id",
            ]
        )
        for r in qs:
            w.writerow(
                [
                    r.external_id,
                    r.amount,
                    r.currency,
                    r.status,
                    r.risk_state,
                    r.initiated_at.isoformat(),
                    r.expected_by.isoformat() if r.expected_by else "",
                    (r.customer.email if r.customer else ""),
                    (r.order.external_id if r.order else ""),
                    (r.transaction.external_id if r.transaction else ""),
                ]
            )

    return ExportResult(export=export, abs_path=abs_path)


def create_dispute_evidence_pack_pdf(dispute_id: int) -> ExportResult:
    dispute = Dispute.objects.select_related("workspace", "customer", "order", "transaction").get(id=dispute_id)
    ws_id = dispute.workspace_id
    filename = _safe_filename(f"evidence_pack_{dispute.external_id}", "pdf")
    abs_path = _exports_dir() / filename

    export = ExportPack.objects.create(
        workspace_id=ws_id,
        type="evidence_pack_pdf",
        status=ExportPack.STATUS_READY,
        file_path=str(abs_path),
    )

    _render_evidence_pack_pdf(abs_path, dispute)
    return ExportResult(export=export, abs_path=abs_path)


def _render_overdue_refunds_pdf(abs_path: Path, refunds: Iterable[Refund]) -> None:
    c = canvas.Canvas(str(abs_path), pagesize=A4)
    width, height = A4

    y = height - 20 * mm
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, y, "Overdue Refunds Report")
    y -= 8 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    y -= 10 * mm

    headers = ["Refund ID", "Amount", "Status", "Initiated", "Expected By", "Customer Email"]
    col_x = [20 * mm, 55 * mm, 80 * mm, 110 * mm, 140 * mm, 170 * mm]

    c.setFont("Helvetica-Bold", 9)
    for hx, htxt in zip(col_x, headers):
        c.drawString(hx, y, htxt)
    y -= 5 * mm
    c.setLineWidth(0.3)
    c.line(20 * mm, y, width - 20 * mm, y)
    y -= 6 * mm

    c.setFont("Helvetica", 8)
    count = 0
    for r in refunds:
        if y < 20 * mm:
            c.showPage()
            y = height - 20 * mm
            c.setFont("Helvetica-Bold", 9)
            for hx, htxt in zip(col_x, headers):
                c.drawString(hx, y, htxt)
            y -= 5 * mm
            c.line(20 * mm, y, width - 20 * mm, y)
            y -= 6 * mm
            c.setFont("Helvetica", 8)

        amount = f"{r.amount/100:.2f} {r.currency}" if r.currency else str(r.amount)
        c.drawString(col_x[0], y, r.external_id[:18])
        c.drawString(col_x[1], y, amount[:14])
        c.drawString(col_x[2], y, r.status[:10])
        c.drawString(col_x[3], y, r.initiated_at.strftime("%Y-%m-%d"))
        c.drawString(col_x[4], y, r.expected_by.strftime("%Y-%m-%d") if r.expected_by else "-")
        c.drawString(col_x[5], y, (r.customer.email if r.customer else "-")[:22])
        y -= 5 * mm
        count += 1

    y -= 8 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y, f"Total overdue refunds: {count}")
    c.save()


def _render_evidence_pack_pdf(abs_path: Path, dispute: Dispute) -> None:
    c = canvas.Canvas(str(abs_path), pagesize=A4)
    width, height = A4
    y = height - 18 * mm

    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, y, "Dispute Evidence Pack")
    y -= 8 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"Dispute ID: {dispute.external_id}")
    y -= 5 * mm
    c.drawString(20 * mm, y, f"Provider: {dispute.provider}    Status: {dispute.status}")
    y -= 5 * mm
    c.drawString(20 * mm, y, f"Amount: {dispute.amount/100:.2f} {dispute.currency}")
    y -= 5 * mm
    if dispute.deadline_at:
        c.drawString(20 * mm, y, f"Deadline: {dispute.deadline_at.strftime('%Y-%m-%d')}")
        y -= 5 * mm

    c.setLineWidth(0.4)
    c.line(20 * mm, y, width - 20 * mm, y)
    y -= 8 * mm

    # Linked entities summary
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, "Linked context")
    y -= 6 * mm
    c.setFont("Helvetica", 10)
    cust = dispute.customer
    if cust:
        c.drawString(20 * mm, y, f"Customer: {cust.email or '-'}  {cust.name or ''}")
        y -= 5 * mm
    if dispute.order:
        c.drawString(20 * mm, y, f"Order: {dispute.order.external_id}  Status: {dispute.order.status}")
        y -= 5 * mm
    if dispute.transaction:
        c.drawString(20 * mm, y, f"Transaction: {dispute.transaction.external_id}  Status: {dispute.transaction.status}")
        y -= 5 * mm

    y -= 4 * mm
    c.setLineWidth(0.3)
    c.line(20 * mm, y, width - 20 * mm, y)
    y -= 8 * mm

    # Evidence checklist
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, "Evidence checklist")
    y -= 6 * mm

    items = dispute.evidence_items.all().prefetch_related("files")
    c.setFont("Helvetica", 10)

    for item in items:
        if y < 25 * mm:
            c.showPage()
            y = height - 18 * mm
            c.setFont("Helvetica-Bold", 12)
            c.drawString(20 * mm, y, "Evidence checklist (cont.)")
            y -= 8 * mm
            c.setFont("Helvetica", 10)

        status = item.status.upper()
        c.drawString(20 * mm, y, f"- {item.type}  [{status}]")
        y -= 5 * mm
        if item.notes:
            c.setFont("Helvetica", 9)
            c.drawString(25 * mm, y, f"Notes: {item.notes[:90]}")
            y -= 5 * mm
            c.setFont("Helvetica", 10)

        for f in item.files.all():
            c.setFont("Helvetica", 9)
            c.drawString(30 * mm, y, f"File: {f.filename} ({f.mime_type or 'unknown'})")
            y -= 4 * mm
            c.setFont("Helvetica", 10)

        y -= 2 * mm

    y -= 6 * mm
    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, y, f"Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    c.save()
