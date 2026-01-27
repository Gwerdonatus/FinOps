from django.contrib import admin
from .models import Customer, Order, PaymentTransaction, Refund

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("workspace", "external_id", "email", "name")
    search_fields = ("external_id", "email", "name")
    list_filter = ("workspace",)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("workspace", "external_id", "provider", "status", "amount", "currency", "created_at")
    search_fields = ("external_id",)
    list_filter = ("provider", "status", "workspace")

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("workspace", "external_id", "provider", "status", "amount", "currency", "initiated_at")
    search_fields = ("external_id",)
    list_filter = ("provider", "status", "workspace")

@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ("workspace", "external_id", "provider", "status", "risk_state", "amount", "currency", "initiated_at", "expected_by")
    search_fields = ("external_id",)
    list_filter = ("provider", "status", "risk_state", "workspace")
