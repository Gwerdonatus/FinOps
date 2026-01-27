from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import datetime as dt

import requests


@dataclass
class ShopifyCredentials:
    shop_domain: str  # e.g. my-store.myshopify.com
    admin_token: str
    api_version: str = "2024-10"


class ShopifyClient:
    def __init__(self, creds: ShopifyCredentials):
        self.creds = creds
        self.base_url = f"https://{creds.shop_domain}/admin/api/{creds.api_version}"
        self.session = requests.Session()
        self.session.headers.update({
            "X-Shopify-Access-Token": creds.admin_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def test_connection(self) -> Dict[str, Any]:
        r = self.session.get(f"{self.base_url}/shop.json", timeout=20)
        r.raise_for_status()
        shop = r.json().get("shop", {})
        return {"name": shop.get("name"), "domain": shop.get("domain"), "currency": shop.get("currency")}

    def list_orders(self, days: int = 30, limit: int = 250) -> List[Dict[str, Any]]:
        created_min = (dt.datetime.utcnow() - dt.timedelta(days=days)).isoformat() + "Z"
        params = {"status": "any", "limit": limit, "created_at_min": created_min}
        r = self.session.get(f"{self.base_url}/orders.json", params=params, timeout=30)
        r.raise_for_status()
        return r.json().get("orders", [])
