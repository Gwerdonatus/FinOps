from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
from xml.sax.saxutils import escape

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.exports.models import ExportPack
from apps.ops_disputes.models import Dispute
from apps.ops_refunds.models import Refund
from apps.ops_refunds.templatetags.money import format_money


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
    return f"{prefix}_{ts}_{uuid4().hex}.{ext}"


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
    dispute = Dispute.objects.select_related("workspace", "customer", "order", "transaction").get(
        id=dispute_id
    )
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


def _report(path, title, subtitle, content):
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    story = [
        Paragraph(escape(title), styles["Title"]),
        Paragraph(escape(subtitle), styles["Normal"]),
        Spacer(1, 8 * mm),
        *content,
    ]

    def footer(canvas, doc):
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(
            18 * mm, 10 * mm, "FinOps | Operations evidence | Review before submission"
        )
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")

    document.build(story, onFirstPage=footer, onLaterPages=footer)


def _paragraph(value, style="Normal"):
    return Paragraph(escape(str(value)), getSampleStyleSheet()[style])


def _render_overdue_refunds_pdf(abs_path: Path, refunds: Iterable[Refund]) -> None:
    records = list(refunds)
    rows = [
        [
            _paragraph(text, "Heading5")
            for text in ["Refund / customer", "Amount", "Status", "Expected by"]
        ]
    ]
    for refund in records:
        rows.append(
            [
                _paragraph(
                    refund.external_id + " / " + (refund.customer.email if refund.customer else "-")
                ),
                _paragraph(format_money(refund.amount, refund.currency)),
                _paragraph(refund.status),
                _paragraph(refund.expected_by.strftime("%Y-%m-%d") if refund.expected_by else "-"),
            ]
        )
    table = Table(rows, colWidths=[70 * mm, 35 * mm, 30 * mm, 39 * mm], repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
            ]
        )
    )
    content = [table, Spacer(1, 8 * mm), _paragraph(f"Total overdue refunds: {len(records)}")]
    if any(refund.raw_payload.get("synthetic") for refund in records):
        content.insert(0, _paragraph("DEMO DATA: staged records, not production refunds."))
        content.insert(1, Spacer(1, 5 * mm))
    _report(
        abs_path,
        "Overdue Refunds Report",
        f"Generated {timezone.now():%Y-%m-%d %H:%M UTC}",
        content,
    )


def _render_evidence_pack_pdf(abs_path: Path, dispute: Dispute) -> None:
    content = []
    if dispute.raw_payload.get("synthetic"):
        content.extend(
            [
                _paragraph("DEMO DATA: synthetic dispute; not submitted to a provider."),
                Spacer(1, 5 * mm),
            ]
        )
    for label, value in [
        ("Dispute", dispute.external_id),
        ("Provider", dispute.provider),
        ("Status", dispute.status),
        ("Reason", dispute.reason),
        ("Amount", format_money(dispute.amount, dispute.currency)),
        ("Deadline", str(dispute.deadline_at or "Not supplied")),
        ("Customer", dispute.customer.email if dispute.customer else "Not linked"),
        ("Order", dispute.order.external_id if dispute.order else "Not linked"),
        ("Payment", dispute.transaction.external_id if dispute.transaction else "Not linked"),
    ]:
        content.append(_paragraph(f"{label}: {value}"))
        content.append(Spacer(1, 2 * mm))
    content.extend([Spacer(1, 5 * mm), _paragraph("Evidence checklist", "Heading2")])
    for item in dispute.evidence_items.all().prefetch_related("files"):
        content.append(
            _paragraph(f"{item.type.replace('_', ' ').title()}: {item.status}", "Heading3")
        )
        content.append(_paragraph(item.notes or "No notes recorded."))
        for file in item.files.all():
            content.append(_paragraph(f"File reference: {file.filename}"))
        content.append(Spacer(1, 3 * mm))
    content.extend(
        [
            Spacer(1, 5 * mm),
            _paragraph(
                "This summary is not proof that evidence is complete or that a dispute has been won. File upload and provider submission are not implemented."
            ),
        ]
    )
    _report(
        abs_path, "Dispute Evidence Pack", f"Generated {timezone.now():%Y-%m-%d %H:%M UTC}", content
    )
