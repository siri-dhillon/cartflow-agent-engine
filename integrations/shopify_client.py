from typing import Optional, Dict, Any
import requests
from config import settings


class ShopifyManager:
    """
    Shopify Storefront API client for cart creation, checkout generation, and discount code application.
    """

    def __init__(
        self,
        store_domain: Optional[str] = None,
        storefront_token: Optional[str] = None,
        use_mocks: Optional[bool] = None,
    ):
        self.store_domain = store_domain or settings.SHOPIFY_STORE_DOMAIN
        self.storefront_token = storefront_token or settings.SHOPIFY_STOREFRONT_TOKEN
        self.use_mocks = use_mocks if use_mocks is not None else settings.USE_MOCKS

    def _graphql_request(self, query: str, variables: Optional[dict] = None) -> dict:
        """Execute a GraphQL query/mutation against the Shopify Storefront API."""
        if not self.store_domain or not self.storefront_token:
            raise ValueError("Shopify store domain and storefront token must be configured.")

        url = f"https://{self.store_domain}/api/2024-01/graphql.json"
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Storefront-Access-Token": self.storefront_token,
        }
        response = requests.post(
            url,
            json={"query": query, "variables": variables or {}},
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def create_cart(self, variant_id: str, quantity: int = 1) -> dict:
        """
        Create a Shopify cart using the cartCreate GraphQL mutation.
        Falls back to a realistic mock cart response if USE_MOCKS is True or API request fails.
        """
        if not self.use_mocks and self.store_domain and self.storefront_token:
            mutation = """
            mutation cartCreate($input: CartInput!) {
              cartCreate(input: $input) {
                cart {
                  id
                  checkoutUrl
                  cost {
                    subtotalAmount {
                      amount
                      currencyCode
                    }
                  }
                }
                userErrors {
                  field
                  message
                }
              }
            }
            """
            variables = {
                "input": {
                    "lines": [
                        {
                            "merchandiseId": variant_id,
                            "quantity": quantity,
                        }
                    ]
                }
            }
            try:
                res = self._graphql_request(mutation, variables)
                cart_data = res.get("data", {}).get("cartCreate", {}).get("cart")
                if cart_data:
                    return {
                        "cart_id": cart_data.get("id"),
                        "checkoutUrl": cart_data.get("checkoutUrl"),
                        "subtotal": float(cart_data.get("cost", {}).get("subtotalAmount", {}).get("amount", 0.0)),
                        "currency": cart_data.get("cost", {}).get("subtotalAmount", {}).get("currencyCode", "USD"),
                        "status": "created",
                    }
            except Exception:
                pass  # Fall back to mock response on failure

        # Realistic mock fallback
        mock_cart_id = f"gid://shopify/Cart/mock_cart_{variant_id.replace('/', '_').replace(':', '_')}"
        domain = self.store_domain or "mock-store.myshopify.com"
        mock_checkout_url = f"https://{domain}/cart/c/mock-checkout-889922"
        mock_subtotal = round(89.99 * quantity, 2)

        return {
            "cart_id": mock_cart_id,
            "checkoutUrl": mock_checkout_url,
            "subtotal": mock_subtotal,
            "currency": "USD",
            "lines": [
                {
                    "variant_id": variant_id,
                    "quantity": quantity,
                }
            ],
            "status": "created",
            "is_mock": True,
        }

    def apply_discount(self, cart_id: str, discount_code: str) -> dict:
        """
        Apply a discount code to a Shopify cart via cartDiscountCodesUpdate mutation.
        """
        if not self.use_mocks and self.store_domain and self.storefront_token:
            mutation = """
            mutation cartDiscountCodesUpdate($cartId: ID!, $discountCodes: [String!]) {
              cartDiscountCodesUpdate(cartId: $cartId, discountCodes: $discountCodes) {
                cart {
                  id
                  checkoutUrl
                  cost {
                    subtotalAmount {
                      amount
                      currencyCode
                    }
                    totalAmount {
                      amount
                      currencyCode
                    }
                  }
                }
                userErrors {
                  field
                  message
                }
              }
            }
            """
            variables = {
                "cartId": cart_id,
                "discountCodes": [discount_code],
            }
            try:
                res = self._graphql_request(mutation, variables)
                cart_data = res.get("data", {}).get("cartDiscountCodesUpdate", {}).get("cart")
                if cart_data:
                    return {
                        "cart_id": cart_data.get("id"),
                        "discount_code": discount_code,
                        "subtotal": float(cart_data.get("cost", {}).get("subtotalAmount", {}).get("amount", 0.0)),
                        "total": float(cart_data.get("cost", {}).get("totalAmount", {}).get("amount", 0.0)),
                        "checkoutUrl": cart_data.get("checkoutUrl"),
                        "status": "discount_applied",
                    }
            except Exception:
                pass  # Fall back to mock response on failure

        # Realistic mock fallback
        domain = self.store_domain or "mock-store.myshopify.com"
        mock_subtotal = 89.99
        mock_discount = 13.50
        mock_total = round(mock_subtotal - mock_discount, 2)

        return {
            "cart_id": cart_id,
            "discount_code": discount_code,
            "subtotal": mock_subtotal,
            "discount_amount": mock_discount,
            "total": mock_total,
            "checkoutUrl": f"https://{domain}/cart/c/mock-checkout-889922?discount={discount_code}",
            "status": "discount_applied",
            "is_mock": True,
        }
