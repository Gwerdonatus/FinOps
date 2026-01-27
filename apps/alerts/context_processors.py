from __future__ import annotations

from typing import Any, Dict

from .models import Alert


def alerts_nav(request) -> Dict[str, Any]:
    ws = getattr(request, "workspace", None)
    if not request.user.is_authenticated or not ws:
        return {"unread_alert_count": 0, "nav_alerts": []}

    qs = Alert.objects.filter(workspace=ws, resolved_at__isnull=True).order_by("-created_at")
    unread = qs.filter(is_read=False).count()
    latest = list(qs[:5])
    return {"unread_alert_count": unread, "nav_alerts": latest}
