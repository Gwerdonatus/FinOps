from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.ops_disputes.models import AIConfiguration
from apps.providers.services.crypto import encrypt_json
from apps.workspaces.models import Workspace

from .forms import PaystackConnectForm, ShopifyConnectForm, StripeConnectForm
from .models import ProviderConnection
from .paystack.client import PaystackClient, PaystackCredentials
from .services.crypto import CredentialEncryptionError
from .services.sync import (
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
        "ai_configured": AIConfiguration.objects.filter(workspace=ws).exists(),
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
    if request.workspace_role != "admin":
        messages.error(request, "Only workspace admins can configure providers.")
        return redirect("providers:connections")
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
            if not secret_key.startswith("sk_test_"):
                messages.error(request, "Stripe requires a sandbox key starting with sk_test_.")
                return redirect("providers:connections")

            webhook_secret = request.POST.get("webhook_secret", "").strip()
            if webhook_secret and not webhook_secret.startswith("whsec_"):
                messages.error(request, "Webhook signing secrets must start with whsec_.")
                return redirect("providers:connections")
            conn.set_credentials(
                {
                    "secret_key": secret_key,
                    "webhook_secret": webhook_secret,
                }
            )
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
            conn.account_id = info.get("id", "")
            conn.save(update_fields=["status", "account_id"])
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
    except Exception:
        messages.error(request, "Connection test failed. Check credentials and network.")
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
                f"Stripe sync complete ✅ Imported {result['transactions']} txns and {result['refunds']} refunds and {result['disputes']} disputes.",
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
    except Exception:
        messages.error(request, "Sync failed. Check credentials and network, then retry.")
        return redirect("providers:connections")


@login_required
def stripe_seed_demo(request):
    messages.info(
        request,
        "Use the local seed_demo command. FinOps does not create provider payments or refunds.",
    )
    return redirect("providers:connections")


@login_required
def configure_ai(request):
    if request.method != "POST" or request.workspace_role != "admin":
        messages.error(request, "Only workspace admins can configure the AI service.")
        return redirect("providers:connections")
    key = request.POST.get("api_key", "").strip()
    if not key.startswith("sk-") or len(key) < 20:
        messages.error(request, "Enter a valid OpenAI API key.")
        return redirect("providers:connections")
    AIConfiguration.objects.update_or_create(
        workspace=request.workspace,
        defaults={"credentials_encrypted": encrypt_json({"api_key": key})},
    )
    messages.success(
        request,
        "OpenAI key stored encrypted. Case sources are sent only when you request a draft and confirm sharing.",
    )
    return redirect("providers:connections")
