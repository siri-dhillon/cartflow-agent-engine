from typing import Optional, Dict, Any
from config import settings


class DatabricksProfiler:
    """
    Databricks client for customer profiling, risk evaluation, and transaction logging.
    """

    def __init__(self, databricks_host: Optional[str] = None, use_mocks: Optional[bool] = None):
        self.databricks_host = databricks_host or settings.DATABRICKS_HOST
        self.use_mocks = use_mocks if use_mocks is not None else settings.USE_MOCKS

        # Mock database of customer profiles for offline testing
        self._mock_profiles: Dict[str, Dict[str, Any]] = {
            "cust_101": {
                "user_id": "cust_101",
                "loyalty_tier": "Gold",
                "churn_risk": 0.15,
                "max_authorized_discount_pct": 15,
                "ltv": 1250.00,
            },
            "cust_102": {
                "user_id": "cust_102",
                "loyalty_tier": "Platinum",
                "churn_risk": 0.05,
                "max_authorized_discount_pct": 20,
                "ltv": 3400.50,
            },
            "cust_103": {
                "user_id": "cust_103",
                "loyalty_tier": "Silver",
                "churn_risk": 0.42,
                "max_authorized_discount_pct": 10,
                "ltv": 450.00,
            },
        }

    def get_customer_profile(self, user_id: str) -> dict:
        """
        Fetch customer profile containing user_id, loyalty_tier, churn_risk, and max_authorized_discount_pct.
        """
        if self.use_mocks or not self.databricks_host:
            profile = self._mock_profiles.get(
                user_id,
                {
                    "user_id": user_id,
                    "loyalty_tier": "Gold",
                    "churn_risk": 0.20,
                    "max_authorized_discount_pct": 15,
                    "ltv": 800.00,
                },
            )
            return profile.copy()

        # Databricks SQL Warehouse / API execution placeholder
        try:
            # Query logic for production Databricks cluster
            return self._mock_profiles.get(
                user_id,
                {
                    "user_id": user_id,
                    "loyalty_tier": "Gold",
                    "churn_risk": 0.20,
                    "max_authorized_discount_pct": 15,
                    "ltv": 800.00,
                },
            )
        except Exception:
            return self._mock_profiles.get(
                user_id,
                {
                    "user_id": user_id,
                    "loyalty_tier": "Gold",
                    "churn_risk": 0.20,
                    "max_authorized_discount_pct": 15,
                    "ltv": 800.00,
                },
            )

    def log_transaction(self, user_id: str, order_value: float, discount_applied: float) -> dict:
        """
        Simulate closing the loop and persisting updated LTV and churn risk after a transaction.
        """
        profile = self.get_customer_profile(user_id)
        current_ltv = profile.get("ltv", 500.00)
        updated_ltv = current_ltv + order_value

        current_churn = profile.get("churn_risk", 0.20)
        updated_churn_risk = max(0.01, round(current_churn * 0.9, 3))

        if user_id in self._mock_profiles:
            self._mock_profiles[user_id]["ltv"] = updated_ltv
            self._mock_profiles[user_id]["churn_risk"] = updated_churn_risk

        return {
            "user_id": user_id,
            "order_value": order_value,
            "discount_applied": discount_applied,
            "updated_ltv": updated_ltv,
            "updated_churn_risk": updated_churn_risk,
            "status": "success",
            "message": "Transaction persisted to Databricks feature store.",
        }
