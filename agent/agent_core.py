import os
import sys
import time
import json
import asyncio
from typing import List, Dict, Any, Optional

# Ensure root directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
from agent.tools import (
    TOOL_FUNCTIONS,
    GEMINI_TOOLS,
    get_customer_profile,
    search_catalog_loomi,
    create_discounted_checkout,
)

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


SYSTEM_PROMPT = """You are CartFlow Agent, an autonomous, margin-aware checkout assistant for an e-commerce platform.

Operating Directives:
1. Always query Bloomreach Loomi MCP using `search_catalog_loomi` for product inquiries or catalog recommendations.
2. When a user exhibits price resistance, hesitates on cost, or requests a discount, query Databricks using `get_customer_profile` to fetch their loyalty tier and allowable discount margin (`max_authorized_discount_pct`).
3. NEVER offer or apply a discount higher than the customer's `max_authorized_discount_pct`.
4. Execute `create_discounted_checkout` to generate a 1-click checkout URL, apply the dynamic discount code, and log the completed intent.
5. Deliver a concise, persuasive response containing the 1-click checkout URL.
"""


class CartFlowAgent:
    """
    Autonomous, margin-aware checkout agent core using google-genai SDK.
    Prioritizes Vertex AI Application Default Credentials (ADC).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-1.5-flash",
        use_mocks: Optional[bool] = None,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
    ):
        self.api_key = api_key or getattr(settings, "GEMINI_API_KEY", None)
        self.model_name = model_name
        self.use_mocks = use_mocks if use_mocks is not None else getattr(settings, "USE_MOCKS", False)
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-04-f50badd76af6")
        self.location = location or os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        self.client = None

        if GENAI_AVAILABLE and not self.use_mocks:
            # 1. Try Vertex AI with Application Default Credentials (ADC)
            use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "true").lower() in ("true", "1", "yes")
            if use_vertex or not self.api_key:
                try:
                    self.client = genai.Client(
                        vertexai=True,
                        project=self.project_id,
                        location=self.location,
                    )
                except Exception:
                    self.client = None

            # 2. Fall back to AI Studio API key if Vertex AI failed to initialize
            if not self.client and self.api_key:
                try:
                    self.client = genai.Client(api_key=self.api_key)
                except Exception:
                    self.client = None

    async def process_message(
        self,
        user_id: str,
        message: str,
        telemetry_sink: list
    ) -> str:
        """
        Process an incoming message through the function call loop, capture telemetry into
        telemetry_sink, and return the final response string.
        """
        if self.client and not self.use_mocks:
            try:
                return await self._process_genai_loop(user_id, message, telemetry_sink)
            except Exception as e:
                telemetry_sink.append({
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "event": "genai_api_fallback",
                    "reason": str(e),
                })

        # Deterministic mock/fallback loop
        return await self._process_mock_loop(user_id, message, telemetry_sink)

    async def _process_genai_loop(
        self,
        user_id: str,
        message: str,
        telemetry_sink: list
    ) -> str:
        """Execute agent tool-calling loop using Google GenAI SDK over Vertex AI ADC."""
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=GEMINI_TOOLS,
            temperature=0.2,
        )

        chat = self.client.chats.create(model=self.model_name, config=config)
        prompt_with_context = f"[Customer ID: {user_id}]\nCustomer message: {message}"
        response = chat.send_message(prompt_with_context)

        max_turns = 5
        turn_count = 0

        while response.function_calls and turn_count < max_turns:
            turn_count += 1
            function_responses = []

            for call in response.function_calls:
                func_name = call.name
                func_args = dict(call.args) if call.args else {}

                # Guarantee user_id parameter for user-specific tools
                if func_name in ("get_customer_profile", "create_discounted_checkout") and "user_id" not in func_args:
                    func_args["user_id"] = user_id

                tool_start_time = time.time()
                tool_fn = TOOL_FUNCTIONS.get(func_name)

                if tool_fn:
                    try:
                        if asyncio.iscoroutinefunction(tool_fn):
                            result = await tool_fn(**func_args)
                        else:
                            result = tool_fn(**func_args)
                    except Exception as exc:
                        result = {"error": f"Tool execution failed: {str(exc)}"}
                else:
                    result = {"error": f"Tool '{func_name}' not defined in TOOL_FUNCTIONS."}

                duration_ms = round((time.time() - tool_start_time) * 1000, 2)

                # Capture telemetry audit
                telemetry_sink.append({
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "event": "tool_execution",
                    "tool": func_name,
                    "arguments": func_args,
                    "result": result,
                    "duration_ms": duration_ms,
                })

                function_responses.append(
                    types.Part.from_function_response(
                        name=func_name,
                        response={"result": result}
                    )
                )

            # Pass tool execution outputs back to the Gemini model
            response = chat.send_message(function_responses)

        return response.text or "I have processed your request."

    async def _process_mock_loop(
        self,
        user_id: str,
        message: str,
        telemetry_sink: list
    ) -> str:
        """Deterministic agent loop when offline or running in mock mode."""
        msg_lower = message.lower()
        is_discount_request = any(
            kw in msg_lower
            for kw in ["discount", "deal", "expensive", "cheaper", "coupon", "price", "too high", "hesitate", "cost", "lower", "budget"]
        )
        is_buy_request = any(
            kw in msg_lower
            for kw in ["buy", "checkout", "cart", "order", "purchase", "get", "link"]
        )

        # 1. Query Loomi MCP Catalog
        cat_start = time.time()
        search_query = message if len(message) < 40 else "running shoes"

        try:
            if asyncio.iscoroutinefunction(search_catalog_loomi):
                catalog_results = await search_catalog_loomi(query=search_query)
            else:
                catalog_results = search_catalog_loomi(query=search_query)
        except Exception as e:
            catalog_results = [{"title": search_query, "price": 49.99, "variant_id": "gid://shopify/ProductVariant/401122334455", "description": str(e)}]

        telemetry_sink.append({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": "tool_execution",
            "tool": "search_catalog_loomi",
            "arguments": {"query": search_query},
            "result": catalog_results,
            "duration_ms": round((time.time() - cat_start) * 1000, 2),
        })

        # Extract product details using Loomi schema
        product = {
            "variant_id": "gid://shopify/ProductVariant/401122334455",
            "title": "Catalog Product",
            "price": 49.99,
            "description": "High performance catalog selection."
        }

        if isinstance(catalog_results, list) and len(catalog_results) > 0:
            item = catalog_results[0]
            if isinstance(item, dict):
                item_data = item.get("data", {}) if isinstance(item.get("data"), dict) else {}
                product["title"] = (
                    item.get("title")
                    or item_data.get("title")
                    or item_data.get("name")
                    or product["title"]
                )
                product["price"] = float(item.get("price") or item.get("_parsedPrice") or item_data.get("price") or product["price"])
                product["variant_id"] = str(item.get("variant_id") or item.get("itemId") or product["variant_id"])
                product["description"] = item.get("description") or item_data.get("description") or product["description"]

        # 2. Query Databricks customer profile on price hesitation or buy intent
        customer_profile = None
        if is_discount_request or is_buy_request:
            db_start = time.time()
            if asyncio.iscoroutinefunction(get_customer_profile):
                customer_profile = await get_customer_profile(user_id)
            else:
                customer_profile = get_customer_profile(user_id)

            telemetry_sink.append({
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "event": "tool_execution",
                "tool": "get_customer_profile",
                "arguments": {"user_id": user_id},
                "result": customer_profile,
                "duration_ms": round((time.time() - db_start) * 1000, 2),
            })

        # 3 & 4. Enforce margin cap & generate 1-click checkout
        if customer_profile and (is_discount_request or is_buy_request):
            max_discount_pct = float(customer_profile.get("max_authorized_discount_pct", 15.0))
            tier = customer_profile.get("loyalty_tier", "Gold")
            discount_code = f"{tier.upper()}{int(max_discount_pct)}"

            chk_start = time.time()
            chk_kwargs = {
                "user_id": user_id,
                "variant_id": product.get("variant_id"),
                "discount_code": discount_code,
                "discount_pct": max_discount_pct
            }
            if asyncio.iscoroutinefunction(create_discounted_checkout):
                checkout_res = await create_discounted_checkout(**chk_kwargs)
            else:
                checkout_res = create_discounted_checkout(**chk_kwargs)

            telemetry_sink.append({
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "event": "tool_execution",
                "tool": "create_discounted_checkout",
                "arguments": chk_kwargs,
                "result": checkout_res,
                "duration_ms": round((time.time() - chk_start) * 1000, 2),
            })

            return (
                f"I found the **{product.get('title')}** for you!\n\n"
                f"As a valued **{tier}** member, I've applied an authorized **{int(max_discount_pct)}% discount**:\n"
                f"• Subtotal: ${product.get('price'):.2f}\n"
                f"• Discounted Total: **${checkout_res.get('final_price'):.2f}** (Code: `{discount_code}`)\n\n"
                f"Complete your order here: [1-Click Checkout]({checkout_res.get('checkout_url')})"
            )

        return (
            f"Here is what I found in our Bloomreach Loomi catalog:\n\n"
            f"**{product.get('title')}** — ${product.get('price'):.2f}\n"
            f"{product.get('description')}\n\n"
            f"Would you like me to check your account for eligible discounts and generate a checkout link?"
        )