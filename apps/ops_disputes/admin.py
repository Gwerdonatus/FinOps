from django.contrib import admin

from .models import Dispute, EvidenceFile, EvidenceItem


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = (
        "workspace",
        "external_id",
        "provider",
        "status",
        "amount",
        "currency",
        "deadline_at",
    )
    search_fields = ("external_id",)
    list_filter = ("provider", "status", "workspace")


@admin.register(EvidenceItem)
class EvidenceItemAdmin(admin.ModelAdmin):
    list_display = ("dispute", "type", "status")
    list_filter = ("type", "status")


@admin.register(EvidenceFile)
class EvidenceFileAdmin(admin.ModelAdmin):
    list_display = ("item", "filename", "uploaded_at")
