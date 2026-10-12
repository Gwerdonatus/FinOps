"""Single Compose process periodically refreshes refund deadline risk."""

import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from apps.ops_refunds.services.risk import apply_risk_for_workspace
from apps.workspaces.models import Workspace


class Command(BaseCommand):
    help = "Refresh workspace refund deadlines every minute."

    def handle(self, *args, **options):
        while True:
            close_old_connections()
            updated = 0
            for workspace_id in Workspace.objects.values_list("id", flat=True):
                updated += apply_risk_for_workspace(workspace_id)
            self.stdout.write(f"Refund risk refresh complete: {updated} state changes.")
            time.sleep(60)
