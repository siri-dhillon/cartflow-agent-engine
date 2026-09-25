"""
End-to-End Test Suite for CartFlow Multi-Agent Checkout Engine.

Tests A2A protocol schema, MCP server integrations, specialized agent logic,
and full end-to-end customer conversion journeys.
"""

import pytest
import asyncio
from checkout_agents.src.protocols.a2a_schema import (
    A2AMessage,
    TaskRequest,
    Artifacts,
    AgentID,
    PerformativeEnum,
    ProductItem,
    RiskAssessment,
    DiscountOffer,
    CheckoutDetails,
)
from checkout_agents.src.mcp_servers.bloomreach_server import BloomreachMCPServer
from checkout_agents.src.mcp_servers.databricks_server import DatabricksMCPServer
from checkout_agents.src.mcp_servers.shopify_server import ShopifyMCPServer
from checkout_agents.src.agents.discovery_agent import DiscoveryAgent
from checkout_agents.src.agents.retention_agent import RetentionAgent
from checkout_agents.src.agents.checkout_agent import CheckoutAgent
from checkout_agents.src.agents.concierge_agent import ConciergeAgent
from checkout_agents.src.orchestrator import A2AOrchestrator


@pytest.mark.asyncio
async def test_a2a_schema_serialization():
    """Verify A2AMessage creation, Pydantic validation, and JSON serialization."""
    msg = A2AMessage(
        sender=AgentID.CONCIERGE,
        receiver=AgentID.RETENTION,
        performative=PerformativeEnum.REQUEST,
        content="Test message",
        task=TaskRequest(goal="Test Goal", customer_id="cust_101"),
    )
    dumped = msg.model_dump()
    assert dumped["sender"] == "concierge"
    assert dumped["receiver"] == "retention"
    assert dumped["performative"] == "REQUEST"
    assert dumped["task"]["customer_id"] == "cust_101"

    reloaded = A2AMessage.model_validate(dumped)
    assert reloaded.sender == AgentID.CONCIERGE
    assert reloaded.message_id == msg.message_id


@pytest.mark.asyncio
async def test_bloomreach_mcp_server():
    """Test Bloomreach MCP Server search and suggest capabilities."""
    server = BloomreachMCPServer(use_mocks=True)
    search_res = await server.bloomreach_search(query="running shoes", limit=3)
    assert search_res["status"] == "success"
    assert len(search_res["products"]) > 0
    assert "CloudRunner" in search_res["products"][0]["title"]

    suggest_res = await server.bloomreach_suggest(query="running", customer_id="cust_101")
    assert suggest_res["status"] == "success"
    assert len(suggest_res["suggestions"]) > 0


@pytest.mark.asyncio
async def test_databricks_mcp_server():
    """Test Databricks MCP Server profile lookup, risk evaluation, and margin guardrails."""
    server = DatabricksMCPServer(use_mocks=True)
    profile_res = await server.databricks_get_customer_profile(customer_id="cust_101")
    assert profile_res["status"] == "success"
    assert profile_res["profile"]["loyalty_tier"] == "GOLD"

    risk_res = await server.databricks_evaluate_churn_risk(
        customer_id="cust_101", hesitation_signal=True, cart_value=180.0
    )
    assert risk_res["risk_level"] in ("HIGH", "MEDIUM")

    disc_res = await server.databricks_calculate_max_discount(
        customer_id="cust_101", requested_discount_pct=25.0
    )
    assert disc_res["approved_discount_pct"] <= disc_res["max_authorized_pct"]
    assert disc_res["approved_discount_pct"] == 15.0  # Gold tier cap


@pytest.mark.asyncio
async def test_shopify_mcp_server():
    """Test Shopify MCP Server cart creation, discount application, and checkout link generation."""
    server = ShopifyMCPServer(use_mocks=True)
    cart_res = await server.shopify_create_cart(variant_id="var_101", quantity=1, unit_price=180.0)
    assert cart_res["status"] == "success"
    assert "cart" in cart_res["cart_id"].lower()

    disc_res = await server.shopify_apply_discount(
        cart_id=cart_res["cart_id"], discount_code="GOLD15", subtotal=180.0, discount_pct=15.0
    )
    assert disc_res["discount_amount"] == 27.0
    assert disc_res["total"] == 153.0

    link_res = await server.shopify_generate_checkout_link(
        variant_id="var_101", quantity=1, unit_price=180.0, discount_code="GOLD15", discount_pct=15.0
    )
    assert "checkout" in link_res["checkout_url"]
    assert link_res["total"] == 153.0


@pytest.mark.asyncio
async def test_individual_agents():
    """Test Discovery, Retention, and Checkout agent message handlers directly."""
    disc_agent = DiscoveryAgent()
    ret_agent = RetentionAgent()
    chk_agent = CheckoutAgent()

    # 1. Discovery Agent
    msg_d = A2AMessage(
        sender=AgentID.CONCIERGE,
        receiver=AgentID.DISCOVERY,
        performative=PerformativeEnum.REQUEST,
        content="Show running shoes",
    )
    res_d = await disc_agent.handle_message(msg_d)
    assert res_d.performative == PerformativeEnum.INFORM
    assert len(res_d.artifacts.recommendations) > 0

    # 2. Retention Agent
    msg_r = A2AMessage(
        sender=AgentID.CONCIERGE,
        receiver=AgentID.RETENTION,
        performative=PerformativeEnum.REQUEST,
        content="Price too high",
        task=TaskRequest(goal="Discount", customer_id="cust_101"),
    )
    res_r = await ret_agent.handle_message(msg_r)
    assert res_r.performative == PerformativeEnum.PROPOSE
    assert res_r.artifacts.discount_offer.discount_pct == 15.0

    # 3. Checkout Agent
    msg_c = A2AMessage(
        sender=AgentID.CONCIERGE,
        receiver=AgentID.CHECKOUT,
        performative=PerformativeEnum.REQUEST,
        content="Checkout link",
        artifacts=res_r.artifacts,
    )
    res_c = await chk_agent.handle_message(msg_c)
    assert res_c.performative == PerformativeEnum.CONFIRM
    assert "checkout" in res_c.artifacts.checkout_details.checkout_url


@pytest.mark.asyncio
async def test_end_to_end_customer_journey_price_hesitation():
    """
    Test full multi-agent pipeline when customer exhibits price hesitation / abandonment risk.
    Flow: Concierge -> Discovery -> Retention (Databricks) -> Checkout (Shopify) -> Concierge response.
    """
    orchestrator = A2AOrchestrator()
    result = await orchestrator.process_customer_journey(
        customer_id="cust_101",
        user_message="These marathon shoes look nice, but $180 is a bit too expensive for my budget right now.",
    )

    assert result["intent"] == "HESITATION"
    assert result["telemetry_count"] >= 6  # Multiple A2A exchanges
    assert "artifacts" in result

    artifacts = result["artifacts"]
    assert artifacts["discount_offer"] is not None
    assert artifacts["discount_offer"]["discount_code"] == "GOLD_15"
    assert artifacts["checkout_details"] is not None
    assert "checkout" in artifacts["checkout_details"]["checkout_url"]

    # Verify synthesized concierge response contains discount code and checkout link
    response_text = result["response"]
    assert "GOLD_15" in response_text or "15" in response_text
    assert "Checkout" in response_text or "checkout" in response_text
