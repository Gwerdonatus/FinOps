from django.urls import path
from . import views

app_name = "ops_disputes"

urlpatterns = [
    path("", views.dispute_list, name="list"),
    path("<int:dispute_id>/", views.dispute_detail, name="detail"),
]
