from django.urls import path

from . import views

app_name = "exports"

urlpatterns = [
    path("", views.exports_list, name="list"),
    path("refunds/overdue/pdf/", views.export_overdue_refunds_pdf, name="refunds_overdue_pdf"),
    path("refunds/overdue/csv/", views.export_overdue_refunds_csv, name="refunds_overdue_csv"),
    path("disputes/<int:dispute_id>/evidence-pack/", views.export_dispute_evidence_pack, name="dispute_evidence_pack"),
    path("download/<int:export_id>/", views.export_download, name="download"),
]
