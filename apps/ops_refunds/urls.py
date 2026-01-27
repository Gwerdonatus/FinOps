from django.urls import path
from . import views

app_name = "ops_refunds"

urlpatterns = [
    path("", views.refund_list, name="list"),
    path("<int:refund_id>/", views.refund_detail, name="detail"),
    path("recalc/", views.recalc_risk, name="recalc"),
]
