from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.ops_refunds.models import PaymentTransaction, Refund
from apps.providers.models import ProviderConnection
from apps.workspaces.models import Workspace


def landing(request: HttpRequest) -> HttpResponse:
    return render(request, "landing.html")


def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        email_or_username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=email_or_username, password=password)
        if user is not None:
            login(request, user)
            return redirect("dashboard")
        messages.error(request, "Invalid credentials. Please try again.")

    return render(request, "auth/login.html")


def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("landing")


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    ws = request.workspace

    # Provider is "connected" only after Test success
    has_connection = ProviderConnection.objects.filter(
        workspace=ws, status=ProviderConnection.STATUS_CONNECTED
    ).exists()

    tx_count = PaymentTransaction.objects.filter(workspace=ws).count()
    has_data = tx_count > 0

    refunds = Refund.objects.filter(workspace=ws)
    counts = {
        "SAFE": refunds.filter(risk_state="SAFE").count(),
        "DUE_SOON": refunds.filter(risk_state="DUE_SOON").count(),
        "AT_RISK": refunds.filter(risk_state="AT_RISK").count(),
        "OVERDUE": refunds.filter(risk_state="OVERDUE").count(),
    }

    return render(
        request,
        "dashboard.html",
        {
            "workspace": ws,
            "sla_days": ws.sla_days if ws else None,
            "counts": counts,
            "has_connection": has_connection,
            "has_data": has_data,
            "tx_count": tx_count,
        },
    )


@login_required
def update_sla(request: HttpRequest) -> HttpResponse:
    ws: Workspace = request.workspace
    role = getattr(request, "workspace_role", None)
    if role != "admin":
        messages.error(request, "Only admins can update SLA settings.")
        return redirect("dashboard")

    if request.method == "POST":
        try:
            sla_days = int(request.POST.get("sla_days", ws.sla_days))
            if sla_days < 1 or sla_days > 60:
                raise ValueError("sla out of range")
            ws.sla_days = sla_days
            ws.save(update_fields=["sla_days"])
            messages.success(request, f"Refund SLA updated to {sla_days} days.")
        except Exception:
            messages.error(request, "Invalid SLA value. Use a number between 1 and 60.")
    return redirect("dashboard")
