from django.urls import path
from . import views

app_name = "providers"

urlpatterns = [
    path("", views.connections, name="connections"),
    path("<str:provider>/connect/", views.connect_provider, name="connect"),
    path("<str:provider>/test/", views.test_provider, name="test"),
    path("<str:provider>/sync/", views.sync_provider, name="sync"),
    path("stripe/seed-demo/", views.stripe_seed_demo, name="stripe_seed_demo"),
]
