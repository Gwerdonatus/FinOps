import stripe
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import ProviderConnection, StripeWebhookEvent
from .services.sync import refresh_event


@csrf_exempt
@require_POST
def stripe_webhook(request, connection_id):
    conn = get_object_or_404(ProviderConnection, pk=connection_id, provider="stripe")
    secret = conn.get_credentials().get("webhook_secret", "")
    if conn.status != "connected" or not secret or len(request.body) > 1024 * 1024:
        return JsonResponse({"error": "Webhook unavailable"}, status=400)
    try:
        event = stripe.Webhook.construct_event(
            request.body, request.headers.get("Stripe-Signature", ""), secret
        )
        event = event.to_dict()
        if event.get("livemode") is not False or (
            event.get("account") and event["account"] != conn.account_id
        ):
            return JsonResponse({"error": "Sandbox account mismatch"}, status=400)
        with transaction.atomic():
            conn = ProviderConnection.objects.select_for_update().get(pk=conn.pk)
            _, created = StripeWebhookEvent.objects.get_or_create(
                connection=conn, external_id=event["id"]
            )
            if created:
                refresh_event(conn, event)
        return JsonResponse({"received": True})
    except (ValueError, stripe.SignatureVerificationError, KeyError):
        return JsonResponse({"error": "Invalid event"}, status=400)
    except Exception:
        # Receipt rolls back on failure; a Stripe retry can process it again.
        return JsonResponse({"error": "Retry delivery"}, status=503)
