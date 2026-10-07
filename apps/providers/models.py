from django.db import models

from apps.workspaces.models import Workspace


class ProviderConnection(models.Model):
    PROVIDER_STRIPE = "stripe"
    PROVIDER_PAYSTACK = "paystack"
    PROVIDER_SHOPIFY = "shopify"
    PROVIDER_PAYPAL = "paypal"  # enum only in Phase 1/2

    PROVIDER_CHOICES = [
        (PROVIDER_STRIPE, "Stripe"),
        (PROVIDER_PAYSTACK, "Paystack"),
        (PROVIDER_SHOPIFY, "Shopify"),
        (PROVIDER_PAYPAL, "PayPal"),
    ]

    STATUS_CONNECTED = "connected"
    STATUS_DISCONNECTED = "disconnected"
    STATUS_CHOICES = [
        (STATUS_CONNECTED, "Connected"),
        (STATUS_DISCONNECTED, "Disconnected"),
    ]

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    provider = models.CharField(max_length=30, choices=PROVIDER_CHOICES)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_DISCONNECTED)
    credentials_encrypted = models.TextField(blank=True, default="")  # placeholder for Phase 1/2
    last_sync_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("workspace", "provider")

    def __str__(self) -> str:
        return f"{self.workspace}:{self.provider} ({self.status})"

    def set_credentials(self, data: dict) -> None:
        from apps.providers.services.crypto import encrypt_json

        self.credentials_encrypted = encrypt_json(data)

    def get_credentials(self) -> dict:
        from apps.providers.services.crypto import decrypt_json

        return decrypt_json(self.credentials_encrypted)
