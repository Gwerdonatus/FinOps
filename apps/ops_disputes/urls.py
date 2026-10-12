from django.urls import path

from . import views

app_name = "ops_disputes"

urlpatterns = [
    path("<int:dispute_id>/evidence/<int:item_id>/", views.update_evidence, name="update_evidence"),
    path("", views.dispute_list, name="list"),
    path("<int:dispute_id>/", views.dispute_detail, name="detail"),
]
