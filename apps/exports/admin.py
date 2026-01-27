from django.contrib import admin
from .models import ExportPack

@admin.register(ExportPack)
class ExportPackAdmin(admin.ModelAdmin):
    list_display = ("workspace", "type", "status", "created_at")
    list_filter = ("type", "status", "workspace")
