from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.workspaces.models import Membership, Workspace


class Command(BaseCommand):
    help = "Seed a demo user + workspace (DEV ONLY). Does NOT seed transactions/refunds."

    def handle(self, *args, **options):
        User = get_user_model()

        user, created = User.objects.get_or_create(
            username="demo@finops.local",
            defaults={"email": "demo@finops.local"},
        )
        if created:
            user.set_password("demo1234")
            user.save()

        ws, _ = Workspace.objects.get_or_create(
            name="Demo Store",
            defaults={"slug": "demo-store", "sla_days": 7},
        )

        Membership.objects.get_or_create(
            user=user,
            workspace=ws,
            defaults={"role": Membership.ROLE_ADMIN},
        )

        self.stdout.write(self.style.SUCCESS("Seed complete."))
        self.stdout.write("Login: demo@finops.local / demo1234")
