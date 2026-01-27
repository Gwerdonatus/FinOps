from django.contrib import admin
from .models import ProviderConnection

@admin.register(ProviderConnection)
class ProviderConnectionAdmin(admin.ModelAdmin):
    list_display = ("workspace", "provider", "status", "last_sync_at")
    list_filter = ("provider", "status")
    search_fields = ("workspace__name",)
