from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.workspaces.models import Workspace

from .forms import PaystackConnectForm, ShopifyConnectForm, StripeConnectForm
from .models import ProviderConnection
from .paystack.client import PaystackClient, PaystackCredentials
from .services.crypto import CredentialEncryptionError
from .services.sync import (
    stripe_seed_demo_data,
    stripe_sync_last_days,
    stripe_test_connection,
)
from .shopify.client import ShopifyClient, ShopifyCredentials


def _get_or_create_conn(ws: Workspace, provider: str) -> ProviderConnection:
    conn, _ = ProviderConnection.objects.get_or_create(workspace=ws, provider=provider)
    return conn


def _safe_get_secret_key(conn: ProviderConnection) -> str:
    """
    Reads conn credentials safely.
    Returns '' if missing.
    Raises CredentialEncryptionError if decrypt fails.
    """
    creds = conn.get_credentials() or {}
    return (creds.get("secret_key") or "").strip()


@login_required
def connections(request: HttpRequest) -> HttpResponse:
    ws = request.workspace
    conns = {c.provider: c for c in ProviderConnection.objects.filter(workspace=ws)}

    stripe_conn = conns.get(ProviderConnection.PROVIDER_STRIPE)
    shopify_conn = conns.get(ProviderConnection.PROVIDER_SHOPIFY)
    paystack_conn = conns.get(ProviderConnection.PROVIDER_PAYSTACK)
    paypal_conn = conns.get(ProviderConnection.PROVIDER_PAYPAL)

    context = {
        "stripe_conn": stripe_conn,
        "shopify_conn": shopify_conn,
        "paystack_conn": paystack_conn,
        "paypal_conn": paypal_conn,
        "stripe_form": StripeConnectForm(),
        "shopify_form": ShopifyConnectForm(),
        "paystack_form": PaystackConnectForm(),
        "demo_mode": getattr(settings, "DEMO_MODE", False),
    }
    return render(request, "providers/connections.html", context)


@login_required
def connect_provider(request: HttpRequest, provider: str) -> HttpResponse:
    """
    Save credentials only.

    IMPORTANT: We do NOT claim 'Connected' until user clicks Test and it succeeds.
    """
    ws = request.workspace
    if request.method != "POST":
        return redirect("providers:connections")

    conn = _get_or_create_conn(ws, provider)

    try:
        if provider == ProviderConnection.PROVIDER_STRIPE:
            form = StripeConnectForm(request.POST)
            if not form.is_valid():
                messages.error(request, "Stripe form invalid.")
                return redirect("providers:connections")

            secret_key = (form.cleaned_data["secret_key"] or "").strip()
            if not (secret_key.startswith("sk_test_") or secret_key.startswith("sk_live_")):
                messages.error(request, "Stripe key must start with sk_test_ or sk_live_.")
                return redirect("providers:connections")

            conn.set_credentials({"secret_key": secret_key})
            conn.status = ProviderConnection.STATUS_DISCONNECTED
            conn.save(update_fields=["credentials_encrypted", "status"])
            messages.success(request, "Stripe key saved. Click Test to verify connection.")
            return redirect("providers:connections")

        if provider == ProviderConnection.PROVIDER_SHOPIFY:
            form = ShopifyConnectForm(request.POST)
            if not form.is_valid():
                messages.error(request, "Shopify form invalid.")
                return redirect("providers:connections")

            shop_domain = (form.cleaned_data["shop_domain"] or "").strip()
            admin_token = (form.cleaned_data["admin_token"] or "").strip()
            if not shop_domain:
                messages.error(request, "Shop domain is required.")
                return redirect("providers:connections")
            if not admin_token:
                messages.error(request, "Admin API token is required.")
                return redirect("providers:connections")

            conn.set_credentials(
                {"shop_domain": shop_domain, "admin_token": admin_token, "api_version": "2024-10"}
            )
            conn.status = ProviderConnection.STATUS_DISCONNECTED
            conn.save(update_fields=["credentials_encrypted", "status"])
            messages.success(request, "Shopify token saved. Click Test to verify connection.")
            return redirect("providers:connections")

        if provider == ProviderConnection.PROVIDER_PAYSTACK:
            form = PaystackConnectForm(request.POST)
            if not form.is_valid():
                messages.error(request, "Paystack form invalid.")
                return redirect("providers:connections")

            secret_key = (form.cleaned_data["secret_key"] or "").strip()
            if not (secret_key.startswith("sk_test_") or secret_key.startswith("sk_live_")):
                messages.error(request, "Paystack key must start with sk_test_ or sk_live_.")
                return redirect("providers:connections")

            conn.set_credentials({"secret_key": secret_key})
            conn.status = ProviderConnection.STATUS_DISCONNECTED
            conn.save(update_fields=["credentials_encrypted", "status"])
            messages.success(request, "Paystack key saved. Click Test to verify connection.")
            return redirect("providers:connections")

        messages.error(request, "Unsupported provider.")
        return redirect("providers:connections")

    except CredentialEncryptionError as exc:
        messages.error(request, str(exc))
        return redirect("providers:connections")


@login_required
def test_provider(request: HttpRequest, provider: str) -> HttpResponse:
    if request.method != "POST":
        return redirect("providers:connections")

    conn = _get_or_create_conn(request.workspace, provider)

    try:
        if provider == ProviderConnection.PROVIDER_STRIPE:
            secret_key = _safe_get_secret_key(conn)
            if not secret_key:
                messages.error(request, "No Stripe key saved. Paste it and click Save key first.")
                return redirect("providers:connections")

            info = stripe_test_connection(conn)
            conn.status = ProviderConnection.STATUS_CONNECTED
            conn.save(update_fields=["status"])
            messages.success(request, f"Stripe verified ✅ Account: {info.get('id')}")
            return redirect("providers:connections")

        if provider == ProviderConnection.PROVIDER_SHOPIFY:
            creds = conn.get_credentials() or {}
            shop_domain = (creds.get("shop_domain") or "").strip()
            admin_token = (creds.get("admin_token") or "").strip()
            if not shop_domain or not admin_token:
                messages.error(request, "No Shopify credentials saved. Save domain + token first.")
                return redirect("providers:connections")

            client = ShopifyClient(
                ShopifyCredentials(
                    shop_domain=shop_domain,
                    admin_token=admin_token,
                    api_version=creds.get("api_version", "2024-10"),
                )
            )
            info = client.test_connection()
            conn.status = ProviderConnection.STATUS_CONNECTED
            conn.save(update_fields=["status"])
            messages.success(request, f"Shopify verified ✅ Store: {info.get('name')}")
            return redirect("providers:connections")

        if provider == ProviderConnection.PROVIDER_PAYSTACK:
            creds = conn.get_credentials() or {}
            secret_key = (creds.get("secret_key") or "").strip()
            if not secret_key:
                messages.error(request, "No Paystack key saved. Paste it and click Save key first.")
                return redirect("providers:connections")

            client = PaystackClient(PaystackCredentials(secret_key=secret_key))
            info = client.test_connection()
            if info.get("status") is True:
                conn.status = ProviderConnection.STATUS_CONNECTED
                conn.save(update_fields=["status"])
                messages.success(request, "Paystack verified ✅")
            else:
                messages.warning(request, f"Paystack response: {info.get('message')}")
            return redirect("providers:connections")

        messages.error(request, "Unsupported provider.")
        return redirect("providers:connections")

    except CredentialEncryptionError as exc:
        messages.error(request, str(exc))
        return redirect("providers:connections")
    except Exception as exc:
        messages.error(request, f"Test failed: {exc}")
        return redirect("providers:connections")


@login_required
def sync_provider(request: HttpRequest, provider: str) -> HttpResponse:
    if request.method != "POST":
        return redirect("providers:connections")

    conn = _get_or_create_conn(request.workspace, provider)

    # Require "Connected" (verified) before sync.
    if conn.status != ProviderConnection.STATUS_CONNECTED:
        messages.error(
            request, "Please click Test first. Sync is only available after verification."
        )
        return redirect("providers:connections")

    try:
        if provider == ProviderConnection.PROVIDER_STRIPE:
            result = stripe_sync_last_days(conn, days=30)
            messages.success(
                request,
                f"Stripe sync complete ✅ Imported {result['transactions']} txns and {result['refunds']} refunds.",
            )
            return redirect("providers:connections")

        if provider == ProviderConnection.PROVIDER_SHOPIFY:
            creds = conn.get_credentials() or {}
            client = ShopifyClient(
                ShopifyCredentials(
                    shop_domain=creds["shop_domain"],
                    admin_token=creds["admin_token"],
                    api_version=creds.get("api_version", "2024-10"),
                )
            )
            orders = client.list_orders(days=30)
            messages.success(request, f"Shopify sync wiring next. Retrieved {len(orders)} orders.")
            return redirect("providers:connections")

        if provider == ProviderConnection.PROVIDER_PAYSTACK:
            creds = conn.get_credentials() or {}
            client = PaystackClient(PaystackCredentials(secret_key=creds["secret_key"]))
            txns = client.list_transactions(days=30, per_page=10, page=1)
            messages.success(
                request, f"Paystack sync wiring next. Retrieved {len(txns)} transactions."
            )
            return redirect("providers:connections")

        messages.error(request, "Unsupported provider.")
        return redirect("providers:connections")

    except CredentialEncryptionError as exc:
        messages.error(request, str(exc))
        return redirect("providers:connections")
    except Exception as exc:
        messages.error(request, f"Sync failed: {exc}")
        return redirect("providers:connections")


@login_required
def stripe_seed_demo(request: HttpRequest) -> HttpResponse:
    """
    Stripe is the ONLY provider with demo seeding (for recordings).
    """
    if request.method != "POST":
        return redirect("providers:connections")

    if not getattr(settings, "DEMO_MODE", False):
        messages.error(request, "Demo seed is disabled (set DEMO_MODE=1).")
        return redirect("providers:connections")

    conn = _get_or_create_conn(request.workspace, ProviderConnection.PROVIDER_STRIPE)

    # Require verified Stripe connection first.
    if conn.status != ProviderConnection.STATUS_CONNECTED:
        messages.error(
            request,
            "Please click Test on Stripe first. Demo seed is only available after verification.",
        )
        return redirect("providers:connections")

    try:
        secret_key = _safe_get_secret_key(conn)
        if not secret_key:
            messages.error(
                request, "No Stripe key saved. Paste your sk_test_... key and click Save key first."
            )
            return redirect("providers:connections")

        if not secret_key.startswith("sk_test_"):
            messages.error(request, "For demo seeding, use a Stripe TEST key (sk_test_...).")
            return redirect("providers:connections")

        created_pis, created_refunds = stripe_seed_demo_data(conn, count=250)
        messages.success(
            request,
            f"Generated {created_pis} demo payments and {created_refunds} refunds in Stripe.",
        )

        result = stripe_sync_last_days(conn, days=30)
        messages.success(
            request,
            f"Synced into dashboard: {result['transactions']} txns, {result['refunds']} refunds.",
        )

    except CredentialEncryptionError as exc:
        messages.error(request, str(exc))
    except Exception as exc:
        messages.error(request, f"Demo seed failed: {exc}")

    return redirect("providers:connections")
