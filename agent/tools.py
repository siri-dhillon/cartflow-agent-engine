import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
import httpx

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

try:
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

logger = logging.getLogger("cartflow.tools")


# =====================================================================
# 1. Bloomreach Loomi MCP Catalog Tool
# =====================================================================

async def search_catalog_loomi(query: str) -> List[Dict[str, Any]]:
    """
    Query Bloomreach Loomi Connect MCP server for catalog products
    via streamablehttp_client (Streamable HTTP JSON-RPC).
    """
    endpoint = os.getenv(
        "LOOMI_CONNECT_ENDPOINT",
        "https://uqa.api.exponea.dev/cocoaas/public/api/clarity-search/v1/mcp/019d4917-3c76-7479-9f00-06c620b231bb"
    )
    auth_token = os.getenv("LOOMI_AUTH_TOKEN", "").strip()
    headers = {"Authorization": auth_token} if auth_token else None

    # Fallback product in case of empty search or network failure
    fallback_items = [
        {
            "variant_id": "gid://shopify/ProductVariant/401122334455",
            "title": f"Featured Product matching '{query}'",
            "price": 49.99,
            "category": "Apparel",
            "description": "High-quality catalog item matched by relevance."
        }
    ]

    try:
        kwargs = {}
        if headers:
            kwargs["headers"] = headers

        # In mcp==1.30.0, streamablehttp_client yields (read_stream, write_stream, get_session_id)
        async with streamablehttp_client(endpoint, **kwargs) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                response = await session.call_tool("search_products", arguments={"query": query})

                raw_items = []
                for block in response.content:
                    if hasattr(block, "text") and block.text:
                        try:
                            parsed = json.loads(block.text)
                            if isinstance(parsed, list):
                                raw_items.extend(parsed)
                            elif isinstance(parsed, dict):
                                nested = parsed.get("products") or parsed.get("items") or [parsed]
                                raw_items.extend(nested)
                        except json.JSONDecodeError:
                            raw_items.append({"title": query, "description": block.text, "price": 0.0})

                if not raw_items:
                    return fallback_items

                # Normalize Loomi's schema (_parsedPrice, data.*, itemId/pointId)
                normalized_items = []
                for item in raw_items:
                    if not isinstance(item, dict):
                        continue
                    item_data = item.get("data", {}) if isinstance(item.get("data"), dict) else {}

                    # Extract Title / Name
                    title = (
                        item_data.get("title")
                        or item_data.get("name")
                        or (f"{item_data.get('brand', '')} {item.get('__categories', ['Item'])[0]}".strip()
                            if item.get("__categories") else None)
                        or item.get("title")
                        or "Catalog Product"
                    )

                    # Extract Price
                    price = item.get("_parsedPrice") or item_data.get("price") or item.get("price") or 29.99
                    try:
                        price = float(price)
                    except (ValueError, TypeError):
                        price = 29.99

                    # Extract Variant / Item ID
                    var_id = str(
                        item.get("itemId")
                        or item.get("pointId")
                        or item_data.get("default_sku")
                        or "gid://shopify/ProductVariant/401122334455"
                    )
                    if not var_id.startswith("gid://"):
                        var_id = f"gid://shopify/ProductVariant/{var_id}"

                    description = item_data.get("description") or item.get("description") or ""

                    normalized_items.append({
                        "variant_id": var_id,
                        "title": title,
                        "price": price,
                        "category": item.get("__categories", ["General"])[0] if item.get("__categories") else "General",
                        "description": description
                    })

                return normalized_items if normalized_items else fallback_items

    except Exception as exc:
        logger.error(f"Loomi MCP search failure: {exc}")
        return fallback_items


# =====================================================================
# 2. Databricks Customer Profile & Margin Tool
# =====================================================================

def get_customer_profile(user_id: str) -> Dict[str, Any]:
    """
    Fetch customer profile and allowable margin thresholds from Databricks SQL
    or fall back to deterministic customer tier policies.
    """
    db_host = os.getenv("DATABRICKS_HOST", "").rstrip("/")
    db_token = os.getenv("DATABRICKS_TOKEN", "")
    db_http_path = os.getenv("DATABRICKS_HTTP_PATH", "")

    # Live Databricks SQL execution
    if db_host and db_token and db_http_path:
        endpoint = f"{db_host}/api/2.0/sql/statements"
        headers = {
            "Authorization": f"Bearer {db_token}",
            "Content-Type": "application/json"
        }
        warehouse_id = db_http_path.split("/")[-1]
        query = f"SELECT user_id, loyalty_tier, max_authorized_discount_pct, ltv_score FROM customer_profiles WHERE user_id = '{user_id}' LIMIT 1"
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(endpoint, json={"statement": query, "warehouse_id": warehouse_id}, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    rows = data.get("result", {}).get("data_array", [])
                    if rows:
                        return {
                            "user_id": rows[0][0],
                            "loyalty_tier": rows[0][1],
                            "max_authorized_discount_pct": float(rows[0][2]),
                            "ltv_score": float(rows[0][3])
                        }
        except Exception as e:
            logger.warning(f"Databricks SQL query error: {e}")

    # Deterministic default profile table
    profiles = {
        "cust_101": {"user_id": "cust_101", "loyalty_tier": "Gold", "max_authorized_discount_pct": 20.0, "ltv_score": 850.0},
        "cust_102": {"user_id": "cust_102", "loyalty_tier": "Silver", "max_authorized_discount_pct": 10.0, "ltv_score": 420.0},
        "cust_103": {"user_id": "cust_103", "loyalty_tier": "Bronze", "max_authorized_discount_pct": 5.0, "ltv_score": 150.0},
    }
    return profiles.get(
        user_id,
        {"user_id": user_id, "loyalty_tier": "Standard", "max_authorized_discount_pct": 10.0, "ltv_score": 250.0}
    )


# =====================================================================
# 3. Shopify Storefront Checkout & Attribution Tool
# =====================================================================

def create_discounted_checkout(
    user_id: str,
    variant_id: str,
    discount_code: str,
    discount_pct: float
) -> Dict[str, Any]:
    """
    Generate a 1-click discounted checkout link via Shopify Storefront GraphQL
    or generate an attributed direct checkout URL.
    """
    shop_domain = os.getenv("SHOPIFY_STORE_DOMAIN", "").strip()
    storefront_token = os.getenv("SHOPIFY_STOREFRONT_TOKEN", "").strip()

    # Base pricing defaults
    subtotal = 129.99
    discount_amount = round(subtotal * (discount_pct / 100.0), 2)
    final_price = round(subtotal - discount_amount, 2)

    # Attempt live Shopify Storefront cart mutation
    if shop_domain and storefront_token:
        graphql_endpoint = f"https://{shop_domain}/api/2024-01/graphql.json"
        query = """
        mutation cartCreate($input: CartInput!) {
          cartCreate(input: $input) {
            cart {
              id
              checkoutUrl
            }
            userErrors {
              message
            }
          }
        }
        """
        payload = {
            "query": query,
            "variables": {
                "input": {
                    "lines": [{"merchandiseId": variant_id, "quantity": 1}],
                    "discountCodes": [discount_code]
                }
            }
        }
        try:
            headers = {
                "Content-Type": "application/json",
                "X-Shopify-Storefront-Access-Token": storefront_token
            }
            with httpx.Client(timeout=10.0) as client:
                res = client.post(graphql_endpoint, json=payload, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    cart = data.get("data", {}).get("cartCreate", {}).get("cart")
                    if cart and cart.get("checkoutUrl"):
                        return {
                            "checkout_url": f"{cart['checkoutUrl']}?discount={discount_code}&ref=cartflow_{user_id}",
                            "subtotal": subtotal,
                            "discount_pct": discount_pct,
                            "final_price": final_price,
                            "discount_code": discount_code
                        }
        except Exception as e:
            logger.warning(f"Shopify Storefront Cart API error: {e}")

    # Attributed checkout URL fallback
    clean_variant_id = variant_id.split("/")[-1] if "/" in variant_id else variant_id
    checkout_url = (
        f"https://{shop_domain or 'quickstart-cartflow.myshopify.com'}/cart/"
        f"{clean_variant_id}:1?discount={discount_code}&ref=cartflow_{user_id}"
    )

    return {
        "checkout_url": checkout_url,
        "subtotal": subtotal,
        "discount_pct": discount_pct,
        "final_price": final_price,
        "discount_code": discount_code
    }


# =====================================================================
# 4. Dispatch Table & Gemini OpenAPI Function Declarations
# =====================================================================

TOOL_FUNCTIONS = {
    "search_catalog_loomi": search_catalog_loomi,
    "get_customer_profile": get_customer_profile,
    "create_discounted_checkout": create_discounted_checkout,
}

GEMINI_TOOLS = []
if GENAI_AVAILABLE:
    GEMINI_TOOLS = [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="search_catalog_loomi",
                    description="Query the Bloomreach Loomi catalog to search for products matching a user query.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "query": types.Schema(
                                type="STRING",
                                description="The natural language product search query (e.g. 'running shoes', 'yellow skirt')."
                            )
                        },
                        required=["query"]
                    )
                ),
                types.FunctionDeclaration(
                    name="get_customer_profile",
                    description="Retrieve a customer's loyalty tier, LTV score, and max authorized discount margin from Databricks.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "user_id": types.Schema(
                                type="STRING",
                                description="The unique customer identifier (e.g. 'cust_101')."
                            )
                        },
                        required=["user_id"]
                    )
                ),
                types.FunctionDeclaration(
                    name="create_discounted_checkout",
                    description="Generate a 1-click checkout URL on Shopify applying an authorized discount code and logging customer intent.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "user_id": types.Schema(
                                type="STRING",
                                description="The customer's ID for attribution."
                            ),
                            "variant_id": types.Schema(
                                type="STRING",
                                description="The product variant ID."
                            ),
                            "discount_code": types.Schema(
                                type="STRING",
                                description="The coupon code to apply."
                            ),
                            "discount_pct": types.Schema(
                                type="NUMBER",
                                description="The percentage discount applied, which MUST NOT exceed the customer's max authorized discount."
                            )
                        },
                        required=["user_id", "variant_id", "discount_code", "discount_pct"]
                    )
                )
            ]
        )
    ]