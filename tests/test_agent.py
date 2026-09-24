import os
import sys
import asyncio
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent.tools import (
    get_customer_profile,
    search_catalog_loomi,
    create_discounted_checkout,
)
from agent.agent_core import CartFlowAgent


def test_agent_tools():
    # Test get_customer_profile
    profile = get_customer_profile("cust_101")
    assert profile["user_id"] == "cust_101"
    assert profile["loyalty_tier"] == "Gold"

    # Test search_catalog_loomi
    products = search_catalog_loomi("running shoes")
    assert isinstance(products, list)
    assert len(products) >= 2

    # Test create_discounted_checkout
    checkout = create_discounted_checkout(
        user_id="cust_101",
        variant_id="gid://shopify/ProductVariant/401122334455",
        discount_code="GOLD15",
        discount_pct=15.0,
    )
    assert checkout["status"] == "success"
    assert checkout["discount_pct"] == 15.0
    assert "checkout_url" in checkout
    assert checkout["databricks_log"]["status"] == "success"


@pytest.mark.asyncio
async def test_cartflow_agent_process_message():
    agent = CartFlowAgent(use_mocks=True)
    telemetry = []

    user_id = "cust_101"
    message = "I like these shoes, but they're a bit expensive. Can I get a discount?"

    response = await agent.process_message(user_id=user_id, message=message, telemetry_sink=telemetry)

    assert isinstance(response, str)
    assert "Checkout" in response or "checkout" in response
    assert len(telemetry) >= 3

    # Check telemetry capture
    event_tools = [t["tool"] for t in telemetry if "tool" in t]
    assert "search_catalog_loomi" in event_tools
    assert "get_customer_profile" in event_tools
    assert "create_discounted_checkout" in event_tools
