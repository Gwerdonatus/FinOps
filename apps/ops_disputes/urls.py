from django.urls import path

from . import views

app_name = "ops_disputes"

urlpatterns = [
    path("files/<int:file_id>/", views.download_evidence, name="download_evidence"),
    path("<int:dispute_id>/brief/", views.create_brief, name="create_brief"),
    path(
        "<int:dispute_id>/evidence/<int:item_id>/upload/",
        views.upload_evidence,
        name="upload_evidence",
    ),
    path("<int:dispute_id>/evidence/<int:item_id>/", views.update_evidence, name="update_evidence"),
    path("", views.dispute_list, name="list"),
    path("<int:dispute_id>/", views.dispute_detail, name="detail"),
]
