from django.urls import path
from . import views

app_name = "alerts"

urlpatterns = [
    path("", views.alerts_list, name="list"),
    path("mark-all-read/", views.mark_all_read, name="mark_all_read"),
    path("unread-count/", views.unread_count, name="unread_count"),
    path("nav.json", views.nav_alerts_json, name="nav_json"),
]
