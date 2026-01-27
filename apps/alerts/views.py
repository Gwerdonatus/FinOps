from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render

from .models import Alert


@login_required
def alerts_list(request: HttpRequest) -> HttpResponse:
    ws = request.workspace
    alerts = Alert.objects.filter(workspace=ws).order_by("-created_at")[:200]
    return render(request, "alerts/list.html", {"alerts": alerts})


@login_required
def mark_all_read(request: HttpRequest) -> HttpResponse:
    """
    Allow both GET and POST so UI + old tests won't break.
    """
    ws = request.workspace
    Alert.objects.filter(workspace=ws, is_read=False).update(is_read=True)
    return redirect("alerts:list")


@login_required
def unread_count(request: HttpRequest) -> JsonResponse:
    ws = request.workspace
    count = Alert.objects.filter(workspace=ws, is_read=False, resolved_at__isnull=True).count()
    return JsonResponse({"unread": count})


@login_required
def nav_alerts_json(request: HttpRequest) -> JsonResponse:
    ws = request.workspace
    qs = Alert.objects.filter(workspace=ws, resolved_at__isnull=True).order_by("-created_at")[:5]
    items = [
        {
            "id": a.id,
            "type": a.get_type_display(),
            "severity": a.severity,
            "message": a.message,
            "created_at": a.created_at.isoformat(),
        }
        for a in qs
    ]
    return JsonResponse({"alerts": items})
