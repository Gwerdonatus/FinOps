from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .models import Refund
from .services.risk import recalc_refund_risk_for_workspace


@login_required
def refund_list(request: HttpRequest) -> HttpResponse:
    ws = request.workspace
    status = request.GET.get("status", "").strip().upper()
    qs = (
        Refund.objects.filter(workspace=ws)
        .select_related("customer", "order", "transaction")
        .order_by("-initiated_at")
    )
    if status in {"SAFE", "DUE_SOON", "AT_RISK", "OVERDUE"}:
        qs = qs.filter(risk_state=status)

    statuses = ["ALL", "OVERDUE", "AT_RISK", "DUE_SOON", "SAFE"]
    return render(
        request,
        "refunds/list.html",
        {"refunds": qs[:200], "filter_status": status, "statuses": statuses},
    )


@login_required
def refund_detail(request: HttpRequest, refund_id: int) -> HttpResponse:
    ws = request.workspace
    refund = get_object_or_404(
        Refund.objects.select_related("customer", "order", "transaction"),
        workspace=ws,
        id=refund_id,
    )
    return render(request, "refunds/detail.html", {"refund": refund})


@login_required
def recalc_risk(request: HttpRequest) -> HttpResponse:
    ws = request.workspace
    recalc_refund_risk_for_workspace(ws)
    messages.success(request, "Refund risk recalculated.")
    return redirect("ops_refunds:list")
