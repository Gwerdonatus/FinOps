from django.db import models
from django.utils import timezone

from apps.workspaces.models import Workspace

class ExportPack(models.Model):
    STATUS_QUEUED = "queued"
    STATUS_READY = "ready"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_READY, "Ready"),
        (STATUS_FAILED, "Failed"),
    ]

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    type = models.CharField(max_length=40)  # evidence_pack|refund_report
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_READY)
    file_path = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
