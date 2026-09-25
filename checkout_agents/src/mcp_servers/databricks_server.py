"""
Databricks MCP Server.

Exposes Model Context Protocol (MCP) tools wrapping Databricks Unity Catalog, SQL Warehouse queries,
and ML Model Serving endpoints for customer profiling, churn/abandonment risk evaluation, and margin guardrails.
"""

import os
from typing import Dict, Any, Optional
import httpx


class DatabricksMCPServer:
    """
    Databricks MCP Server implementation.
    Evaluates customer LTV, loyalty tiers, and calculates margin-safe dynamic discount authorization caps.
    """

    MOCK_CUSTOMER_PROFILES: Dict[str, Dict[str, Any]] = {
        "cust_101": {
            "customer_id": "cust_101",
            "name": "Sarah Jenkins",
            "loyalty_tier": "GOLD",
            "ltv_score": 1450.00,
            "total_orders": 12,
            "churn_risk_score": 0.72,
            "max_authorized_discount_pct": 15.0,
            "preferred_category": "Footwear",
        },
        "cust_102": {
            "customer_id": "cust_102",
            "name": "Marcus Vance",
            "loyalty_tier": "PLATINUM",
            "ltv_score": 3800.00,
            "total_orders": 28,
            "churn_risk_score": 0.85,
            "max_authorized_discount_pct": 20.0,
            "preferred_category": "Apparel",
        },
        "cust_103": {
            "customer_id": "cust_103",
            "name": "Emily Chen",
            "loyalty_tier": "STANDARD",
            "ltv_score": 120.00,
            "total_orders": 1,
            "churn_risk_score": 0.30,
            "max_authorized_discount_pct": 5.0,
            "preferred_category": "Accessories",
        },
    }

    def __init__(
        self,
        host: Optional[str] = None,
        token: Optional[str] = None,
        use_mocks: Optional[bool] = None,
    ):
        self.host = host or os.getenv("DATABRICKS_HOST", "")
        self.token = token or os.getenv("DATABRICKS_TOKEN", "")

        env_mocks = os.getenv("USE_MOCKS", "true").lower() in ("true", "1", "t", "yes")
        self.use_mocks = use_mocks if use_mocks is not None else env_mocks

    async def databricks_get_customer_profile(
        self,
        customer_id: str,
    ) -> Dict[str, Any]:
        """
        Query customer profile & LTV metrics from Databricks Unity Catalog / Delta Lake.
        """
        if not self.use_mocks and self.host and self.token:
            try:
                url = f"{self.host.rstrip('/')}/api/2.0/sql/statements"
                headers = {
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "statement": f"SELECT customer_id, name, loyalty_tier, ltv_score, churn_risk_score, max_authorized_discount_pct FROM main.crm.customer_profiles WHERE customer_id = '{customer_id}' LIMIT 1",
                    "warehouse_id": os.getenv("DATABRICKS_WAREHOUSE_ID", "default_wh"),
                }
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    if resp.status_code == 200:
                        res_data = resp.json()
                        rows = res_data.get("result", {}).get("data_array", [])
                        if rows:
                            row = rows[0]
                            return {
                                "status": "success",
                                "customer_id": row[0],
                                "name": row[1],
                                "loyalty_tier": row[2],
                                "ltv_score": float(row[3]),
                                "churn_risk_score": float(row[4]),
                                "max_authorized_discount_pct": float(row[5]),
                            }
            except Exception:
                pass  # Fall back to mock response on failure

        # Fallback to mock profiles
        profile = self.MOCK_CUSTOMER_PROFILES.get(
            customer_id,
            {
                "customer_id": customer_id,
                "name": "Valued Shopper",
                "loyalty_tier": "STANDARD",
                "ltv_score": 250.00,
                "total_orders": 2,
                "churn_risk_score": 0.45,
                "max_authorized_discount_pct": 10.0,
                "preferred_category": "General",
            },
        )
        return {
            "status": "success",
            "profile": profile,
            "is_mock": True,
        }

    async def databricks_evaluate_churn_risk(
        self,
        customer_id: str,
        hesitation_signal: bool = True,
        cart_value: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Evaluate real-time cart abandonment & churn risk score using ML Serving / Rules model.
        """
        profile_res = await self.databricks_get_customer_profile(customer_id)
        profile = profile_res.get("profile", {})
        base_risk = profile.get("churn_risk_score", 0.5)

        # Calculate dynamic risk score adjustment
        adjusted_risk = base_risk
        if hesitation_signal:
            adjusted_risk = min(1.0, adjusted_risk + 0.25)
        if cart_value > 150.0:
            adjusted_risk = min(1.0, adjusted_risk + 0.10)

        risk_level = "HIGH" if adjusted_risk >= 0.7 else ("MEDIUM" if adjusted_risk >= 0.4 else "LOW")

        return {
            "status": "success",
            "customer_id": customer_id,
            "churn_risk_score": round(adjusted_risk, 2),
            "risk_level": risk_level,
            "hesitation_detected": hesitation_signal,
            "cart_value": cart_value,
            "loyalty_tier": profile.get("loyalty_tier", "STANDARD"),
        }

    async def databricks_calculate_max_discount(
        self,
        customer_id: str,
        requested_discount_pct: float = 15.0,
    ) -> Dict[str, Any]:
        """
        Enforce strict margin guardrails to calculate maximum authorized discount percentage.
        """
        profile_res = await self.databricks_get_customer_profile(customer_id)
        profile = profile_res.get("profile", {})
        max_authorized = profile.get("max_authorized_discount_pct", 10.0)
        tier = profile.get("loyalty_tier", "STANDARD")

        approved_pct = min(requested_discount_pct, max_authorized)
        code = f"{tier}_{int(approved_pct)}" if approved_pct > 0 else "WELCOME5"

        return {
            "status": "success",
            "customer_id": customer_id,
            "requested_discount_pct": requested_discount_pct,
            "max_authorized_pct": max_authorized,
            "approved_discount_pct": approved_pct,
            "discount_code": code,
            "loyalty_tier": tier,
            "margin_safe": approved_pct <= max_authorized,
        }
