from django.utils import timezone
from .models import Alert

def create_alert(*, workspace, type, severity, entity_type, entity_id, message) -> Alert:
    return Alert.objects.create(
        workspace=workspace,
        type=type,
        severity=severity,
        entity_type=entity_type,
        entity_id=entity_id,
        message=message,
        created_at=timezone.now(),
    )
