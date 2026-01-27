from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("settings/sla/", views.update_sla, name="update_sla"),
]
