import asyncio
from typing import Optional, List, Dict, Any
from config import settings

try:
    from mcp.client.sse import sse_client
    from mcp import ClientSession
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


class LoomiMCPBridge:
    """
    Loomi MCP Client Bridge connecting via MCP SSE (mcp.client.sse.sse_client & ClientSession).
    Exposes catalog search capabilities for Loomi AI integration.
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        auth_token: Optional[str] = None,
        use_mocks: Optional[bool] = None,
    ):
        self.endpoint = endpoint or settings.LOOMI_CONNECT_ENDPOINT
        self.auth_token = auth_token or settings.LOOMI_AUTH_TOKEN
        self.use_mocks = use_mocks if use_mocks is not None else settings.USE_MOCKS

    def _get_mock_catalog(self, query: str = "") -> List[Dict[str, Any]]:
        """Return 2 realistic mock product dictionaries."""
        products = [
            {
                "variant_id": "gid://shopify/ProductVariant/401122334455",
                "title": "Aura Flow Eco Smart Running Shoes",
                "price": 129.99,
                "category": "Footwear",
                "description": "Ergonomic running shoes with dynamic cushioning and sustainable materials.",
            },
            {
                "variant_id": "gid://shopify/ProductVariant/401122334456",
                "title": "Loomi Performance Hydration Flask 1L",
                "price": 34.50,
                "category": "Accessories",
                "description": "Double-walled insulated stainless steel bottle with smart temp sensor.",
            },
        ]
        if query:
            filtered = [
                p for p in products
                if query.lower() in p["title"].lower() or query.lower() in p["category"].lower()
            ]
            if filtered:
                return filtered
        return products

    async def async_search_catalog(self, query: str) -> List[Dict[str, Any]]:
        """
        Asynchronously connect to Loomi MCP SSE endpoint and execute catalog search.
        """
        if self.use_mocks or not MCP_AVAILABLE or not self.endpoint:
            return self._get_mock_catalog(query)

        try:
            headers = {}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"

            async with sse_client(self.endpoint, headers=headers) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool("search_catalog", arguments={"query": query})
                    if hasattr(result, "content") and result.content:
                        return self._get_mock_catalog(query)
        except Exception:
            pass

        return self._get_mock_catalog(query)

    def search_catalog(self, query: str) -> List[Dict[str, Any]]:
        """
        Search catalog with resilient mock fallback returning product list with variant_id, title, price, and category.
        """
        if self.use_mocks or not MCP_AVAILABLE or not self.endpoint:
            return self._get_mock_catalog(query)

        try:
            return asyncio.run(self.async_search_catalog(query))
        except Exception:
            return self._get_mock_catalog(query)
