from django.core.management.base import BaseCommand

from apps.ops_refunds.models import Refund
from apps.ops_refunds.services.risk import apply_risk_for_workspace


class Command(BaseCommand):
    help = "Recalculate refund risk states for all workspaces (Phase 2/3 demo helper)."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", type=int, default=None)

    def handle(self, *args, **options):
        ws_id = options.get("workspace_id")
        if ws_id:
            updated = apply_risk_for_workspace(ws_id)
            self.stdout.write(self.style.SUCCESS(f"Workspace {ws_id}: updated {updated} refunds"))
            return

        ws_ids = Refund.objects.values_list("workspace_id", flat=True).distinct()
        total = 0
        for wid in ws_ids:
            total += apply_risk_for_workspace(wid)
        self.stdout.write(
            self.style.SUCCESS(f"Updated {total} refunds across {len(set(ws_ids))} workspaces")
        )
