"""
Checkout Transaction Agent.

Specialized transaction closing agent connected to Shopify MCP server (Storefront & Cart GraphQL APIs).
Assembles cart lines, applies authorized dynamic discount codes, and generates 1-click instant checkout links.
"""

from typing import Dict, Any, Optional
from ..protocols.a2a_schema import (
    A2AMessage,
    TaskRequest,
    Artifacts,
    CheckoutDetails,
    AgentID,
    PerformativeEnum,
)
from ..mcp_servers.shopify_server import ShopifyMCPServer


class CheckoutAgent:
    """
    Checkout Agent responsible for cart mutation, discount application, and 1-click checkout generation.
    """

    def __init__(self, shopify_server: Optional[ShopifyMCPServer] = None):
        self.agent_id = AgentID.CHECKOUT
        self.shopify_server = shopify_server or ShopifyMCPServer()

    async def handle_message(self, message: A2AMessage) -> A2AMessage:
        """
        Process incoming A2A message requests to generate 1-click discounted checkout links.
        """
        if message.performative not in (PerformativeEnum.REQUEST, PerformativeEnum.PROPOSE):
            return A2AMessage(
                conversation_id=message.conversation_id,
                sender=self.agent_id,
                receiver=message.sender,
                performative=PerformativeEnum.REJECT,
                content="Checkout Agent accepts REQUEST or PROPOSE performatives.",
            )

        task = message.task or TaskRequest(
            goal="1-Click Checkout Link Generation",
            customer_id="cust_101",
        )

        # Extract items and discount details
        variant_id = "gid://shopify/ProductVariant/v_run_01_m"
        quantity = 1
        unit_price = 180.00
        discount_code = task.discount_code
        discount_pct = 0.0

        if task.cart_items:
            first_item = task.cart_items[0]
            variant_id = first_item.get("variant_id", variant_id)
            quantity = int(first_item.get("quantity", 1))
            unit_price = float(first_item.get("price", unit_price))

        if message.artifacts and message.artifacts.discount_offer:
            discount_code = message.artifacts.discount_offer.discount_code
            discount_pct = message.artifacts.discount_offer.discount_pct
        elif task.metadata.get("discount_pct"):
            discount_pct = float(task.metadata.get("discount_pct"))

        # Invoke Shopify MCP Server
        res = await self.shopify_server.shopify_generate_checkout_link(
            variant_id=variant_id,
            quantity=quantity,
            unit_price=unit_price,
            discount_code=discount_code,
            discount_pct=discount_pct,
        )

        checkout_details = CheckoutDetails(
            cart_id=res.get("cart_id", "cart_0"),
            checkout_url=res.get("checkout_url", "https://checkout.shopify.com"),
            subtotal=res.get("subtotal", unit_price * quantity),
            discount_amount=res.get("discount_amount", 0.0),
            total=res.get("total", unit_price * quantity),
            currency=res.get("currency", "USD"),
            discount_code=discount_code,
            status="created",
        )

        content_msg = (
            f"Generated 1-click checkout link: {checkout_details.checkout_url} "
            f"(Total: ${checkout_details.total:.2f} USD, Savings: ${checkout_details.discount_amount:.2f})"
        )

        return A2AMessage(
            conversation_id=message.conversation_id,
            sender=self.agent_id,
            receiver=message.sender,
            performative=PerformativeEnum.CONFIRM,
            content=content_msg,
            task=task,
            artifacts=Artifacts(checkout_details=checkout_details),
        )
