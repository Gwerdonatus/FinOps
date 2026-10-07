from django.db import models
from django.utils import timezone

from apps.workspaces.models import Workspace


class Customer(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    external_id = models.CharField(max_length=120)
    email = models.EmailField(blank=True, default="")
    name = models.CharField(max_length=120, blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("workspace", "external_id")

    def __str__(self) -> str:
        return self.email or self.external_id


class Order(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    provider = models.CharField(max_length=30, default="shopify")
    external_id = models.CharField(max_length=120)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.BigIntegerField(default=0)  # minor units
    currency = models.CharField(max_length=10, default="NGN")
    status = models.CharField(max_length=30, default="unknown")
    created_at = models.DateTimeField(default=timezone.now)
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("workspace", "external_id")

    def __str__(self) -> str:
        return self.external_id


class PaymentTransaction(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    provider = models.CharField(max_length=30, default="stripe")
    external_id = models.CharField(max_length=120)
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.BigIntegerField(default=0)
    currency = models.CharField(max_length=10, default="NGN")
    status = models.CharField(max_length=30, default="unknown")
    initiated_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("workspace", "external_id")

    def __str__(self) -> str:
        return self.external_id


class Refund(models.Model):
    RISK_SAFE = "SAFE"
    RISK_DUE_SOON = "DUE_SOON"
    RISK_AT_RISK = "AT_RISK"
    RISK_OVERDUE = "OVERDUE"
    RISK_CHOICES = [
        (RISK_SAFE, "Safe"),
        (RISK_DUE_SOON, "Due soon"),
        (RISK_AT_RISK, "At risk"),
        (RISK_OVERDUE, "Overdue"),
    ]

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
    status = models.CharField(max_length=30, default="pending")
    initiated_at = models.DateTimeField(default=timezone.now)
    expected_by = models.DateTimeField(null=True, blank=True)
    last_provider_update_at = models.DateTimeField(null=True, blank=True)
    risk_state = models.CharField(max_length=20, choices=RISK_CHOICES, default=RISK_SAFE)
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("workspace", "external_id")

    def __str__(self) -> str:
        return self.external_id
