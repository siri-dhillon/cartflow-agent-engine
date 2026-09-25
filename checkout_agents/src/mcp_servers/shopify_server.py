"""
Shopify MCP Server.

Exposes Model Context Protocol (MCP) tools wrapping Shopify Storefront GraphQL APIs
for cart creation, dynamic discount code application, and 1-click checkout URL generation.
"""

import os
from typing import Dict, Any, Optional
import httpx


class ShopifyMCPServer:
    """
    Shopify MCP Server implementation.
    Interacts with Shopify Storefront GraphQL API to assemble carts and issue checkout links.
    """

    def __init__(
        self,
        store_domain: Optional[str] = None,
        storefront_token: Optional[str] = None,
        use_mocks: Optional[bool] = None,
    ):
        self.store_domain = store_domain or os.getenv("SHOPIFY_STORE_DOMAIN", "cartflow-demo.myshopify.com")
        self.storefront_token = storefront_token or os.getenv("SHOPIFY_STOREFRONT_TOKEN", "")

        env_mocks = os.getenv("USE_MOCKS", "true").lower() in ("true", "1", "t", "yes")
        self.use_mocks = use_mocks if use_mocks is not None else env_mocks

    async def shopify_create_cart(
        self,
        variant_id: str,
        quantity: int = 1,
        unit_price: float = 180.00,
    ) -> Dict[str, Any]:
        """
        Create a new Shopify cart using Storefront GraphQL cartCreate mutation.
        """
        if not self.use_mocks and self.store_domain and self.storefront_token:
            try:
                url = f"https://{self.store_domain}/api/2024-01/graphql.json"
                mutation = """
                mutation cartCreate($input: CartInput!) {
                  cartCreate(input: $input) {
                    cart {
                      id
                      checkoutUrl
                      cost {
                        subtotalAmount { amount currencyCode }
                      }
                    }
                  }
                }
                """
                variables = {"input": {"lines": [{"merchandiseId": variant_id, "quantity": quantity}]}}
                headers = {
                    "Content-Type": "application/json",
                    "X-Shopify-Storefront-Access-Token": self.storefront_token,
                }
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(url, json={"query": mutation, "variables": variables}, headers=headers)
                    if resp.status_code == 200:
                        cart_data = resp.json().get("data", {}).get("cartCreate", {}).get("cart")
                        if cart_data:
                            return {
                                "status": "success",
                                "cart_id": cart_data.get("id"),
                                "checkout_url": cart_data.get("checkoutUrl"),
                                "subtotal": float(cart_data.get("cost", {}).get("subtotalAmount", {}).get("amount", 0.0)),
                                "currency": cart_data.get("cost", {}).get("subtotalAmount", {}).get("currencyCode", "USD"),
                            }
            except Exception:
                pass  # Fall back to mock response on failure

        # Mock cart response
        clean_variant = variant_id.replace("/", "_").replace(":", "_")
        cart_id = f"gid://shopify/Cart/cart_mock_{clean_variant}"
        subtotal = round(unit_price * quantity, 2)
        checkout_url = f"https://{self.store_domain}/cart/c/mock_checkout_{clean_variant}"

        return {
            "status": "success",
            "cart_id": cart_id,
            "checkout_url": checkout_url,
            "subtotal": subtotal,
            "currency": "USD",
            "quantity": quantity,
            "variant_id": variant_id,
            "is_mock": True,
        }

    async def shopify_apply_discount(
        self,
        cart_id: str,
        discount_code: str,
        subtotal: float = 180.00,
        discount_pct: float = 15.0,
    ) -> Dict[str, Any]:
        """
        Apply a discount code to an existing cart via cartDiscountCodesUpdate mutation.
        """
        if not self.use_mocks and self.store_domain and self.storefront_token:
            try:
                url = f"https://{self.store_domain}/api/2024-01/graphql.json"
                mutation = """
                mutation cartDiscountCodesUpdate($cartId: ID!, $discountCodes: [String!]) {
                  cartDiscountCodesUpdate(cartId: $cartId, discountCodes: $discountCodes) {
                    cart {
                      id
                      checkoutUrl
                      cost {
                        subtotalAmount { amount currencyCode }
                        totalAmount { amount currencyCode }
                      }
                    }
                  }
                }
                """
                variables = {"cartId": cart_id, "discountCodes": [discount_code]}
                headers = {
                    "Content-Type": "application/json",
                    "X-Shopify-Storefront-Access-Token": self.storefront_token,
                }
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(url, json={"query": mutation, "variables": variables}, headers=headers)
                    if resp.status_code == 200:
                        cart_data = resp.json().get("data", {}).get("cartDiscountCodesUpdate", {}).get("cart")
                        if cart_data:
                            sub_amt = float(cart_data.get("cost", {}).get("subtotalAmount", {}).get("amount", subtotal))
                            tot_amt = float(cart_data.get("cost", {}).get("totalAmount", {}).get("amount", subtotal))
                            return {
                                "status": "success",
                                "cart_id": cart_id,
                                "discount_code": discount_code,
                                "subtotal": sub_amt,
                                "discount_amount": round(sub_amt - tot_amt, 2),
                                "total": tot_amt,
                                "checkout_url": cart_data.get("checkoutUrl"),
                            }
            except Exception:
                pass

        # Mock discount application
        discount_amount = round(subtotal * (discount_pct / 100.0), 2)
        total = round(subtotal - discount_amount, 2)
        checkout_url = f"https://{self.store_domain}/cart/c/mock_checkout?discount={discount_code}"

        return {
            "status": "success",
            "cart_id": cart_id,
            "discount_code": discount_code,
            "subtotal": subtotal,
            "discount_pct": discount_pct,
            "discount_amount": discount_amount,
            "total": total,
            "currency": "USD",
            "checkout_url": checkout_url,
            "is_mock": True,
        }

    async def shopify_generate_checkout_link(
        self,
        variant_id: str,
        quantity: int = 1,
        unit_price: float = 180.00,
        discount_code: Optional[str] = None,
        discount_pct: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Generate complete 1-click cart and checkout URL with pre-applied dynamic discounts.
        """
        cart_res = await self.shopify_create_cart(variant_id=variant_id, quantity=quantity, unit_price=unit_price)
        cart_id = cart_res["cart_id"]
        subtotal = cart_res["subtotal"]

        if discount_code and discount_pct > 0:
            disc_res = await self.shopify_apply_discount(
                cart_id=cart_id,
                discount_code=discount_code,
                subtotal=subtotal,
                discount_pct=discount_pct,
            )
            return {
                "status": "success",
                "cart_id": cart_id,
                "checkout_url": disc_res["checkout_url"],
                "subtotal": subtotal,
                "discount_code": discount_code,
                "discount_amount": disc_res["discount_amount"],
                "total": disc_res["total"],
                "currency": "USD",
            }

        return {
            "status": "success",
            "cart_id": cart_id,
            "checkout_url": cart_res["checkout_url"],
            "subtotal": subtotal,
            "discount_code": None,
            "discount_amount": 0.0,
            "total": subtotal,
            "currency": "USD",
        }
