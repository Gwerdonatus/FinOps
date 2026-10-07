from datetime import timedelta

from django.utils import timezone

from apps.alerts.models import Alert
from apps.alerts.services import create_alert
from apps.workspaces.models import Workspace

from ..models import Refund


def compute_expected_by(initiated_at, sla_days: int):
    return initiated_at + timedelta(days=sla_days)


def compute_risk_state(expected_by, now):
    """Time-based SLA risk states for the MVP."""
    delta = expected_by - now
    days_left = delta.total_seconds() / 86400

    if days_left < 0:
        return Refund.RISK_OVERDUE
    if days_left <= 1:
        return Refund.RISK_AT_RISK
    if days_left <= 3:
        return Refund.RISK_DUE_SOON
    return Refund.RISK_SAFE


def apply_risk(refund: Refund, sla_days: int):
    now = timezone.now()
    expected_by = refund.expected_by or compute_expected_by(refund.initiated_at, sla_days)
    new_state = compute_risk_state(expected_by, now)

    old_state = refund.risk_state
    changed = (old_state != new_state) or (refund.expected_by is None)

    if changed:
        refund.expected_by = expected_by
        refund.risk_state = new_state
        refund.save(update_fields=["expected_by", "risk_state"])

        if new_state == Refund.RISK_DUE_SOON:
            create_alert(
                workspace=refund.workspace,
                type=Alert.TYPE_REFUND_DUE_SOON,
                severity=Alert.SEVERITY_WARNING,
                entity_type="refund",
                entity_id=refund.id,
                message=f"Refund {refund.external_id} is due soon (SLA risk).",
            )
        elif new_state == Refund.RISK_OVERDUE:
            create_alert(
                workspace=refund.workspace,
                type=Alert.TYPE_REFUND_OVERDUE,
                severity=Alert.SEVERITY_DANGER,
                entity_type="refund",
                entity_id=refund.id,
                message=f"Refund {refund.external_id} is overdue (chargeback risk).",
            )

    return old_state, new_state


def recalc_refund_risk_for_workspace(workspace: Workspace):
    sla_days = workspace.sla_days
    for refund in Refund.objects.filter(workspace=workspace):
        apply_risk(refund, sla_days)


def apply_risk_for_workspace(workspace_id: int) -> int:
    qs = Refund.objects.filter(workspace_id=workspace_id).select_related("workspace")
    updated = 0
    for refund in qs:
        old_state, new_state = apply_risk(refund, refund.workspace.sla_days)
        if old_state != new_state:
            updated += 1
    return updated
