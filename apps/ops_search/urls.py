from django.urls import path
from . import views

app_name = "ops_search"

urlpatterns = [
    path("", views.search, name="search"),
]
