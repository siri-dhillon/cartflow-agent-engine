"""
Bloomreach MCP Server.

Exposes Model Context Protocol (MCP) tools wrapping Bloomreach Discovery Search & Suggest APIs,
with built-in fallback mock search for offline development and testing.
"""

import os
from typing import List, Dict, Any, Optional
import httpx


class BloomreachMCPServer:
    """
    Bloomreach Discovery MCP Server implementation.
    Wraps product search, auto-suggest, and semantic merchandising discovery.
    """

    MOCK_CATALOG: List[Dict[str, Any]] = [
        {
            "product_id": "prod_run_01",
            "variant_id": "gid://shopify/ProductVariant/v_run_01_m",
            "title": "CloudRunner Pro 2026 Carbon-Plated Running Shoes",
            "price": 180.00,
            "currency": "USD",
            "category": "Footwear",
            "inventory_quantity": 15,
            "score": 0.98,
            "description": "Ultra-lightweight marathon running shoe with carbon fiber plate and reactive foam cushion.",
        },
        {
            "product_id": "prod_run_02",
            "variant_id": "gid://shopify/ProductVariant/v_run_02_m",
            "title": "AeroStride Velocity Daily Trainer",
            "price": 120.00,
            "currency": "USD",
            "category": "Footwear",
            "inventory_quantity": 42,
            "score": 0.91,
            "description": "Durable daily distance running shoe engineered for maximum comfort and high mileage.",
        },
        {
            "product_id": "prod_app_01",
            "variant_id": "gid://shopify/ProductVariant/v_app_01_l",
            "title": "ThermoDry Breathable Running Hoodie",
            "price": 65.00,
            "currency": "USD",
            "category": "Apparel",
            "inventory_quantity": 25,
            "score": 0.85,
            "description": "Moisture-wicking thermal hoodie with thumbholes and reflective safety accents.",
        },
        {
            "product_id": "prod_acc_01",
            "variant_id": "gid://shopify/ProductVariant/v_acc_01_std",
            "title": "HydroGrip Hydration Belt & Flask Kit",
            "price": 45.00,
            "currency": "USD",
            "category": "Accessories",
            "inventory_quantity": 50,
            "score": 0.82,
            "description": "Bounce-free marathon hydration belt including two 300ml ergonomic flasks.",
        },
    ]

    def __init__(
        self,
        account_id: Optional[str] = None,
        domain_key: Optional[str] = None,
        auth_token: Optional[str] = None,
        use_mocks: Optional[bool] = None,
    ):
        self.account_id = account_id or os.getenv("BLOOMREACH_ACCOUNT_ID", "")
        self.domain_key = domain_key or os.getenv("BLOOMREACH_DOMAIN_KEY", "")
        self.auth_token = auth_token or os.getenv("BLOOMREACH_AUTH_TOKEN", "")
        
        env_mocks = os.getenv("USE_MOCKS", "true").lower() in ("true", "1", "t", "yes")
        self.use_mocks = use_mocks if use_mocks is not None else env_mocks

    async def bloomreach_search(
        self,
        query: str,
        category: Optional[str] = None,
        max_price: Optional[float] = None,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """
        Execute catalog search via Bloomreach Discovery API (or mock catalog fallback).
        """
        if not self.use_mocks and self.account_id and self.domain_key:
            try:
                url = f"https://api.connect.bloomreach.com/v1/search"
                params = {
                    "account_id": self.account_id,
                    "domain_key": self.domain_key,
                    "q": query,
                    "rows": limit,
                    "search_type": "keyword",
                }
                headers = {"Authorization": f"Bearer {self.auth_token}"} if self.auth_token else {}
                
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(url, params=params, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        docs = data.get("response", {}).get("docs", [])
                        results = []
                        for d in docs[:limit]:
                            results.append({
                                "product_id": d.get("pid", d.get("id")),
                                "variant_id": d.get("variant_id", f"gid://shopify/ProductVariant/{d.get('pid')}"),
                                "title": d.get("title", d.get("name")),
                                "price": float(d.get("price", 99.99)),
                                "currency": d.get("currency", "USD"),
                                "category": d.get("category", "General"),
                                "inventory_quantity": int(d.get("inventory", 10)),
                                "score": float(d.get("score", 1.0)),
                                "description": d.get("description", ""),
                            })
                        return {"status": "success", "query": query, "count": len(results), "products": results}
            except Exception:
                pass  # Graceful fallback to mock on API error

        # Filtering mock catalog
        query_lower = query.lower()
        matched = []
        for item in self.MOCK_CATALOG:
            title_match = query_lower in item["title"].lower() or any(w in item["title"].lower() for w in query_lower.split())
            desc_match = query_lower in item["description"].lower()
            cat_match = category is None or category.lower() in item["category"].lower()
            price_match = max_price is None or item["price"] <= max_price

            if (title_match or desc_match) and cat_match and price_match:
                matched.append(item)

        if not matched:
            matched = self.MOCK_CATALOG[:limit]  # Fallback to general recommendations

        return {
            "status": "success",
            "query": query,
            "count": len(matched[:limit]),
            "products": matched[:limit],
            "is_mock": True,
        }

    async def bloomreach_suggest(
        self,
        query: str,
        customer_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch search autocomplete and personalized recommendations.
        """
        search_res = await self.bloomreach_search(query=query, limit=3)
        return {
            "status": "success",
            "query": query,
            "suggestions": [p["title"] for p in search_res.get("products", [])],
            "recommended_products": search_res.get("products", []),
            "customer_id": customer_id,
        }
