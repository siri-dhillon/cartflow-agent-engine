import os
import sys
from typing import Dict, Any, List, Optional

# Ensure root directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from integrations.databricks_client import DatabricksProfiler
from integrations.shopify_client import ShopifyManager
from integrations.loomi_mcp_client import LoomiMCPBridge

try:
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# Shared integration client singletons
databricks_profiler = DatabricksProfiler()
shopify_manager = ShopifyManager()
loomi_mcp_bridge = LoomiMCPBridge()


def get_customer_profile(user_id: str) -> dict:
    """
    Query Databricks for customer profile including loyalty tier, churn risk, and max allowable discount margin.

    Args:
        user_id: Unique identifier for the customer (e.g., 'cust_101').

    Returns:
        Dictionary containing user_id, loyalty_tier, churn_risk, and max_authorized_discount_pct.
    """
    return databricks_profiler.get_customer_profile(user_id=user_id)


def search_catalog_loomi(query: str) -> list[dict]:
    """
    Search Bloomreach Loomi MCP for products, variants, and bundle accessories.

    Args:
        query: Search string or product description keywords (e.g., 'running shoes').

    Returns:
        List of product dictionaries containing variant_id, title, price, and category.
    """
    return loomi_mcp_bridge.search_catalog(query=query)


def create_discounted_checkout(
    user_id: str,
    variant_id: str,
    discount_code: str,
    discount_pct: float
) -> dict:
    """
    Mutate Shopify cart, apply dynamic discount, generate 1-click checkout link,
    and log the transaction event back into Databricks to close the feedback loop on customer LTV.

    Args:
        user_id: Customer ID.
        variant_id: Shopify merchandise variant ID.
        discount_code: Discount code to apply (e.g., 'GOLD15').
        discount_pct: Percentage of discount to apply (e.g., 15.0).

    Returns:
        Dictionary containing checkout URL, final price, discount status, and Databricks write-back log.
    """
    # 1. Enforce max authorized discount limit from Databricks
    profile = databricks_profiler.get_customer_profile(user_id)
    max_authorized = float(profile.get("max_authorized_discount_pct", 15))
    effective_discount_pct = min(discount_pct, max_authorized)

    # 2. Mutate Shopify cart
    cart_res = shopify_manager.create_cart(variant_id=variant_id, quantity=1)
    cart_id = cart_res.get("cart_id", "")

    # 3. Apply dynamic discount code
    discount_res = shopify_manager.apply_discount(cart_id=cart_id, discount_code=discount_code)

    # 4. Compute final amounts and log transaction to Databricks to close the loop
    subtotal = discount_res.get("subtotal", 89.99)
    discount_amount = round(subtotal * (effective_discount_pct / 100.0), 2)
    final_price = round(subtotal - discount_amount, 2)

    db_log = databricks_profiler.log_transaction(
        user_id=user_id,
        order_value=final_price,
        discount_applied=effective_discount_pct
    )

    return {
        "status": "success",
        "cart_id": cart_id,
        "variant_id": variant_id,
        "discount_code": discount_code,
        "discount_pct": effective_discount_pct,
        "subtotal": subtotal,
        "final_price": final_price,
        "checkout_url": discount_res.get("checkoutUrl", ""),
        "databricks_log": db_log
    }


# Map function names for tool-dispatching
TOOL_FUNCTIONS = {
    "get_customer_profile": get_customer_profile,
    "search_catalog_loomi": search_catalog_loomi,
    "create_discounted_checkout": create_discounted_checkout,
}

# Python tool list for Gemini API
GEMINI_TOOLS = [
    get_customer_profile,
    search_catalog_loomi,
    create_discounted_checkout,
]
