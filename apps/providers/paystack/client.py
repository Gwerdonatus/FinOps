from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import datetime as dt

import requests


@dataclass
class PaystackCredentials:
    secret_key: str


class PaystackClient:
    BASE_URL = "https://api.paystack.co"

    def __init__(self, creds: PaystackCredentials):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {creds.secret_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def test_connection(self) -> Dict[str, Any]:
        # A lightweight endpoint: list transactions with perPage=1
        r = self.session.get(f"{self.BASE_URL}/transaction", params={"perPage": 1, "page": 1}, timeout=20)
        r.raise_for_status()
        data = r.json()
        return {"status": data.get("status"), "message": data.get("message")}

    def list_transactions(self, days: int = 30, per_page: int = 100, page: int = 1) -> List[Dict[str, Any]]:
        # Paystack uses offset pagination (page/perPage). 'from'/'to' are supported by some endpoints; if not, we still fetch latest pages.
        r = self.session.get(
            f"{self.BASE_URL}/transaction",
            params={"perPage": per_page, "page": page},
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("data", []) or []

    def list_refunds(self, per_page: int = 100, page: int = 1) -> List[Dict[str, Any]]:
        r = self.session.get(
            f"{self.BASE_URL}/refund",
            params={"perPage": per_page, "page": page},
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("data", []) or []
