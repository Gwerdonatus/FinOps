from django.db import models
from django.utils import timezone

from apps.ops_refunds.models import Customer, Order, PaymentTransaction
from apps.workspaces.models import Workspace


class Dispute(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    provider = models.CharField(max_length=30, default="stripe")
    external_id = models.CharField(max_length=120)

    transaction = models.ForeignKey(
        PaymentTransaction, on_delete=models.SET_NULL, null=True, blank=True
    )
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)

    amount = models.BigIntegerField(default=0)
    currency = models.CharField(max_length=10, default="NGN")
    status = models.CharField(max_length=30, default="unknown")
    reason = models.CharField(max_length=60, blank=True, default="")
    deadline_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("workspace", "external_id")

    def __str__(self) -> str:
        return self.external_id


class EvidenceItem(models.Model):
    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name="evidence_items")
    type = models.CharField(max_length=40)  # e.g., policy, comms, delivery, refund_proof
    status = models.CharField(max_length=20, default="missing")  # missing|uploaded
    notes = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        return f"{self.dispute.external_id}:{self.type}"


class EvidenceFile(models.Model):
    item = models.ForeignKey(EvidenceItem, on_delete=models.CASCADE, related_name="files")
    file_path = models.CharField(max_length=300)  # placeholder (S3/local later)
    filename = models.CharField(max_length=200)
    mime_type = models.CharField(max_length=80, blank=True, default="")
    uploaded_at = models.DateTimeField(default=timezone.now)
