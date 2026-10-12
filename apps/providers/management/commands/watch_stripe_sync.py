import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from apps.providers.models import ProviderConnection
from apps.providers.services.sync import stripe_sync_last_days


class Command(BaseCommand):
    help = "Read-only Stripe sandbox synchronization every five minutes."

    def handle(self, *args, **options):
        while True:
            close_old_connections()
            for conn in ProviderConnection.objects.filter(provider="stripe", status="connected"):
                try:
                    counts = stripe_sync_last_days(conn)
                    self.stdout.write(
                        f"Stripe sandbox sync complete for connection {conn.id}: {counts}"
                    )
                except Exception:
                    self.stderr.write(
                        f"Stripe sandbox sync failed for connection {conn.id}; retrying next cycle."
                    )
            time.sleep(300)
