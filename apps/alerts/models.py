from django.db import models
from django.utils import timezone

from apps.workspaces.models import Workspace


class Alert(models.Model):
    SEVERITY_INFO = "info"
    SEVERITY_WARNING = "warning"
    SEVERITY_DANGER = "danger"
    SEVERITY_CHOICES = [
        (SEVERITY_INFO, "Info"),
        (SEVERITY_WARNING, "Warning"),
        (SEVERITY_DANGER, "Danger"),
    ]

    TYPE_REFUND_DUE_SOON = "refund_due_soon"
    TYPE_REFUND_AT_RISK = "refund_at_risk"
    TYPE_REFUND_OVERDUE = "refund_overdue"
    TYPE_CHOICES = [
        (TYPE_REFUND_DUE_SOON, "Refund due soon"),
        (TYPE_REFUND_AT_RISK, "Refund at risk"),
        (TYPE_REFUND_OVERDUE, "Refund overdue"),
    ]

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    type = models.CharField(max_length=60, choices=TYPE_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default=SEVERITY_INFO)
    entity_type = models.CharField(max_length=60)
    entity_id = models.PositiveIntegerField()
    message = models.CharField(max_length=240)
    created_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)
    is_read = models.BooleanField(default=False)

    @property
    def is_resolved(self) -> bool:
        return self.resolved_at is not None

    def __str__(self) -> str:
        return f"{self.type} ({self.severity})"
