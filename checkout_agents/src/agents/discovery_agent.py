"""
Discovery Merchandising Agent.

Specialized merchandising agent connected to Bloomreach MCP server and catalog inventory.
Executes semantic vector search, category filtering, and product recommendation generation.
"""

from typing import Dict, Any, Optional
from ..protocols.a2a_schema import (
    A2AMessage,
    TaskRequest,
    Artifacts,
    ProductItem,
    AgentID,
    PerformativeEnum,
)
from ..mcp_servers.bloomreach_server import BloomreachMCPServer


class DiscoveryAgent:
    """
    Discovery Agent responsible for product search, recommendations, and inventory lookup.
    """

    def __init__(self, bloomreach_server: Optional[BloomreachMCPServer] = None):
        self.agent_id = AgentID.DISCOVERY
        self.bloomreach_server = bloomreach_server or BloomreachMCPServer()

    async def handle_message(self, message: A2AMessage) -> A2AMessage:
        """
        Process incoming A2A message requests for product catalog search.
        """
        if message.performative != PerformativeEnum.REQUEST:
            return A2AMessage(
                conversation_id=message.conversation_id,
                sender=self.agent_id,
                receiver=message.sender,
                performative=PerformativeEnum.REJECT,
                content="Discovery Agent only accepts REQUEST performative.",
            )

        task = message.task or TaskRequest(
            goal="Product Search",
            customer_id="cust_guest",
            query=message.content,
        )

        query = task.query or message.content or "running shoes"
        category = task.metadata.get("category")
        max_price = task.metadata.get("max_price")

        # Execute Bloomreach MCP search
        search_result = await self.bloomreach_server.bloomreach_search(
            query=query,
            category=category,
            max_price=max_price,
            limit=4,
        )

        raw_products = search_result.get("products", [])
        product_items = []
        for p in raw_products:
            product_items.append(
                ProductItem(
                    product_id=p.get("product_id", "prod_0"),
                    variant_id=p.get("variant_id", "var_0"),
                    title=p.get("title", "Product"),
                    price=float(p.get("price", 99.99)),
                    currency=p.get("currency", "USD"),
                    category=p.get("category", "General"),
                    inventory_quantity=int(p.get("inventory_quantity", 10)),
                    score=float(p.get("score", 1.0)),
                )
            )

        summary_text = (
            f"Found {len(product_items)} items matching '{query}'"
            if product_items
            else f"No catalog matches found for '{query}'."
        )

        return A2AMessage(
            conversation_id=message.conversation_id,
            sender=self.agent_id,
            receiver=message.sender,
            performative=PerformativeEnum.INFORM,
            content=summary_text,
            task=task,
            artifacts=Artifacts(recommendations=product_items),
        )
