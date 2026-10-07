from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import stripe


@dataclass
class StripeCredentials:
    secret_key: str


class StripeClient:
    def __init__(self, creds: StripeCredentials):
        stripe.api_key = creds.secret_key
        # Use account default API version; you can pin if desired.
        self._stripe = stripe

    def test_connection(self) -> dict[str, Any]:
        acct = self._stripe.Account.retrieve()
        return {"id": acct.get("id"), "email": acct.get("email"), "country": acct.get("country")}

    def list_payment_intents(
        self, created_gte: int | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if created_gte:
            params["created"] = {"gte": created_gte}
        res = self._stripe.PaymentIntent.list(**params)
        return list(res.auto_paging_iter())

    def list_refunds(
        self, created_gte: int | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if created_gte:
            params["created"] = {"gte": created_gte}
        res = self._stripe.Refund.list(**params)
        return list(res.auto_paging_iter())

    def create_demo_payment_intent(
        self, *, amount: int, currency: str, email: str
    ) -> dict[str, Any]:
        customer = self._stripe.Customer.create(email=email)
        pi = self._stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            customer=customer["id"],
            payment_method="pm_card_visa",
            confirm=True,
            off_session=True,
            description="FinOps demo seed",
        )
        return pi

    def create_refund_for_payment_intent(
        self, payment_intent_id: str, amount: int | None = None
    ) -> dict[str, Any]:
        # Need a charge id to refund. PaymentIntent includes latest_charge.
        pi = self._stripe.PaymentIntent.retrieve(payment_intent_id)
        charge_id = pi.get("latest_charge")
        if not charge_id:
            # sometimes the charge is in charges list
            charges = pi.get("charges", {}).get("data", [])
            if charges:
                charge_id = charges[0].get("id")
        if not charge_id:
            raise RuntimeError("Could not locate charge for payment intent to refund.")
        refund = (
            self._stripe.Refund.create(charge=charge_id, amount=amount)
            if amount
            else self._stripe.Refund.create(charge=charge_id)
        )
        return refund
