from django.conf import settings
from django.db import models
from django.utils.text import slugify

class Workspace(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    timezone = models.CharField(max_length=64, default="UTC")
    sla_days = models.PositiveIntegerField(default=7)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:140]
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name

class Membership(models.Model):
    ROLE_ADMIN = "admin"
    ROLE_AGENT = "agent"
    ROLE_CHOICES = [
        (ROLE_ADMIN, "Admin"),
        (ROLE_AGENT, "Agent"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_ADMIN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "workspace")

    def __str__(self) -> str:
        return f"{self.user} @ {self.workspace} ({self.role})"
