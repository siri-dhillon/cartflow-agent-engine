import os
import sys
import pytest

# Ensure project root is on sys.path for direct pytest invocation
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from integrations.databricks_client import DatabricksProfiler
from integrations.shopify_client import ShopifyManager
from integrations.loomi_mcp_client import LoomiMCPBridge


def test_databricks_profiler_mock():
    profiler = DatabricksProfiler(use_mocks=True)

    # Test get_customer_profile for cust_101
    profile = profiler.get_customer_profile("cust_101")
    assert profile["user_id"] == "cust_101"
    assert profile["loyalty_tier"] == "Gold"
    assert isinstance(profile["churn_risk"], float)
    assert profile["churn_risk"] == 0.15
    assert profile["max_authorized_discount_pct"] == 15

    # Test fallback profile for unknown customer
    fallback = profiler.get_customer_profile("cust_unknown")
    assert fallback["user_id"] == "cust_unknown"
    assert fallback["loyalty_tier"] == "Gold"
    assert fallback["max_authorized_discount_pct"] == 15

    # Test log_transaction
    log_res = profiler.log_transaction(user_id="cust_101", order_value=200.0, discount_applied=30.0)
    assert log_res["status"] == "success"
    assert log_res["user_id"] == "cust_101"
    assert log_res["order_value"] == 200.0
    assert log_res["discount_applied"] == 30.0
    assert log_res["updated_ltv"] > 1250.0
    assert log_res["updated_churn_risk"] < 0.15


def test_shopify_manager_mock():
    shopify = ShopifyManager(use_mocks=True)

    # Test create_cart
    variant_id = "gid://shopify/ProductVariant/401122334455"
    cart = shopify.create_cart(variant_id=variant_id, quantity=2)
    assert "cart_id" in cart
    assert "checkoutUrl" in cart
    assert "subtotal" in cart
    assert cart["status"] == "created"
    assert cart["subtotal"] > 0.0
    assert cart["checkoutUrl"].startswith("https://")

    # Test apply_discount
    discount_res = shopify.apply_discount(cart_id=cart["cart_id"], discount_code="GOLD15")
    assert discount_res["cart_id"] == cart["cart_id"]
    assert discount_res["discount_code"] == "GOLD15"
    assert discount_res["status"] == "discount_applied"
    assert "checkoutUrl" in discount_res
    assert discount_res["subtotal"] > discount_res["total"]


def test_loomi_mcp_bridge_mock():
    bridge = LoomiMCPBridge(use_mocks=True)

    # Test search_catalog
    products = bridge.search_catalog("running shoes")
    assert isinstance(products, list)
    assert len(products) >= 2

    for product in products:
        assert "variant_id" in product
        assert "title" in product
        assert "price" in product
        assert "category" in product
        assert isinstance(product["price"], (int, float))
        assert product["variant_id"].startswith("gid://shopify/ProductVariant/")
