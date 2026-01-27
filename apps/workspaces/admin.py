from django.contrib import admin
from .models import Workspace, Membership

@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "timezone", "sla_days", "created_at")
    search_fields = ("name", "slug")

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "workspace", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email", "workspace__name")
