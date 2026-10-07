from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.accounts import views as account_views

urlpatterns = [
    path("admin/", admin.site.urls),
    # Public
    path("", account_views.landing, name="landing"),
    path("login/", account_views.login_view, name="login"),
    path("logout/", account_views.logout_view, name="logout"),
    # App shell
    path("app/", account_views.dashboard, name="dashboard"),
    path("app/settings/sla/", account_views.update_sla, name="update_sla"),
    # Modules
    path("app/connections/", include("apps.providers.urls")),
    path("app/refunds/", include("apps.ops_refunds.urls")),
    path("app/search/", include("apps.ops_search.urls")),
    path("app/disputes/", include("apps.ops_disputes.urls")),
    path("app/exports/", include("apps.exports.urls")),
    path("app/alerts/", include("apps.alerts.urls")),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
