from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from apps.ops_refunds.models import Customer, Order, PaymentTransaction, Refund
from apps.ops_disputes.models import Dispute

@login_required
def search(request: HttpRequest) -> HttpResponse:
    ws = request.workspace
    q = (request.GET.get("q") or "").strip()

    result = {
        "customer": None,
        "orders": [],
        "transactions": [],
        "refunds": [],
        "disputes": [],
    }

    if q:
        if "@" in q:
            result["customer"] = Customer.objects.filter(workspace=ws, email__iexact=q).first()
        else:
            # Try exact external IDs across entities
            result["transactions"] = list(PaymentTransaction.objects.filter(workspace=ws, external_id=q)[:5])
            result["orders"] = list(Order.objects.filter(workspace=ws, external_id=q)[:5])
            result["refunds"] = list(Refund.objects.filter(workspace=ws, external_id=q)[:5])
            result["disputes"] = list(Dispute.objects.filter(workspace=ws, external_id=q)[:5])

        # If we found a customer, load related entities for the unified story
        cust = result["customer"]
        if cust:
            result["orders"] = list(Order.objects.filter(workspace=ws, customer=cust).order_by("-created_at")[:5])
            result["transactions"] = list(
                PaymentTransaction.objects.filter(workspace=ws, customer=cust).order_by("-initiated_at")[:5]
            )
            result["refunds"] = list(Refund.objects.filter(workspace=ws, customer=cust).order_by("-initiated_at")[:5])
            result["disputes"] = list(Dispute.objects.filter(workspace=ws, customer=cust).order_by("-deadline_at")[:5])

    return render(request, "search/search.html", {"q": q, "result": result})
