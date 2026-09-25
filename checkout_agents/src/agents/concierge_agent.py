"""
Concierge Coordinator Agent.

Primary conversational coordinator powered by Google GenAI SDK (`google-genai`) and `gemini-2.5-flash`.
Evaluates customer intent, orchestrates specialized sub-agents via A2A protocol bus,
and synthesizes persuasive, conversion-driving responses to minimize cart abandonment.
"""

import os
from typing import Dict, Any, Optional, List
from google import genai
from google.genai import types

from ..protocols.a2a_schema import (
    A2AMessage,
    TaskRequest,
    Artifacts,
    AgentID,
    PerformativeEnum,
)


class ConciergeAgent:
    """
    Concierge Coordinator Agent responsible for dialogue management, intent understanding,
    and A2A multi-agent task dispatching.
    """

    SYSTEM_PROMPT = """You are CartFlow Concierge, an expert e-commerce shopping advisor and checkout assistant.
Your mission is to maximize conversion and eliminate cart abandonment with warm, helpful, concise, and persuasive guidance.

Guiding Principles:
1. When recommending products, highlight key performance features and exact prices.
2. When a customer hesitates on price or requests a discount, introduce personalized loyalty rewards empathetically and present the approved discount code clearly.
3. Always include the 1-click checkout URL when cart links are available so the shopper can complete their purchase effortlessly.
4. Keep responses under 4 sentences. Be direct, enthusiastic, and conversion-focused.
"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        use_mocks: Optional[bool] = None,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
    ):
        self.agent_id = AgentID.CONCIERGE
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-04-f50badd76af6")
        self.location = location or os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        self.use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "true").lower() in ("true", "1", "yes")
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        env_mocks = os.getenv("USE_MOCKS", "false").lower() in ("true", "1", "t", "yes")
        self.use_mocks = use_mocks if use_mocks is not None else env_mocks

        self.genai_client = None
        if not self.use_mocks:
            try:
                # 1. Prioritize Vertex AI Application Default Credentials (ADC)
                if self.use_vertex or self.project_id:
                    self.genai_client = genai.Client(
                        vertexai=True,
                        project=self.project_id,
                        location=self.location,
                    )
                elif self.api_key:
                    self.genai_client = genai.Client(api_key=self.api_key)
            except Exception:
                self.genai_client = None

    def classify_intent(self, user_message: str) -> str:
        """
        Classify customer message intent into DISCOVERY, HESITATION, or CHECKOUT.
        """
        msg_lower = user_message.lower()

        hesitation_words = ["expensive", "too high", "cost", "discount", "coupon", "price", "cheaper", "budget", "think about it", "hesitate"]
        checkout_words = ["buy", "checkout", "link", "cart", "pay", "order", "purchase", "take it"]

        if any(w in msg_lower for w in hesitation_words):
            return "HESITATION"
        elif any(w in msg_lower for w in checkout_words):
            return "CHECKOUT"
        else:
            return "DISCOVERY"

    async def generate_response(
        self,
        user_message: str,
        artifacts: Artifacts,
        customer_id: str = "cust_101",
    ) -> str:
        """
        Generate final customer-facing response using Google GenAI SDK or deterministic fallback.
        """
        # Context summary string
        ctx_lines = [f"Customer Message: {user_message}"]

        if artifacts.recommendations:
            prod_summary = ", ".join([f"{p.title} (${p.price})" for p in artifacts.recommendations])
            ctx_lines.append(f"Product Recommendations: {prod_summary}")

        if artifacts.discount_offer:
            offer = artifacts.discount_offer
            ctx_lines.append(f"Approved Dynamic Discount: {offer.discount_pct}% off with code '{offer.discount_code}' ({offer.reason})")

        if artifacts.checkout_details:
            chk = artifacts.checkout_details
            ctx_lines.append(f"Instant Checkout URL: {chk.checkout_url} (Final Total: ${chk.total:.2f} {chk.currency})")

        prompt_context = "\n".join(ctx_lines)

        if self.genai_client and not self.use_mocks:
            try:
                config = types.GenerateContentConfig(
                    system_instruction=self.SYSTEM_PROMPT,
                    temperature=0.4,
                    max_output_tokens=300,
                )
                response = self.genai_client.models.generate_content(
                    model=self.model_name,
                    contents=prompt_context,
                    config=config,
                )
                if response and response.text:
                    return response.text.strip()
            except Exception:
                pass  # Fall back to deterministic template on API failure

        # Deterministic Fallback Generator
        if artifacts.checkout_details:
            chk = artifacts.checkout_details
            if artifacts.discount_offer:
                disc = artifacts.discount_offer
                return (
                    f"Great news! I've unlocked an exclusive {disc.discount_pct}% reward discount for you. "
                    f"Use code **{disc.discount_code}** to get your order for just **${chk.total:.2f} USD**. "
                    f"Complete your order instantly here: [1-Click Checkout]({chk.checkout_url})"
                )
            return (
                f"Your item is ready! Subtotal: **${chk.subtotal:.2f} USD**. "
                f"You can complete your instant 1-click checkout right here: [Complete Order]({chk.checkout_url})"
            )

        if artifacts.recommendations:
            top_prod = artifacts.recommendations[0]
            return (
                f"I highly recommend the **{top_prod.title}** (${top_prod.price:.2f} USD). "
                f"It features top-tier performance materials with ready inventory. Would you like me to set up a 1-click checkout cart for you?"
            )

        return f"Thank you for contacting CartFlow! How can I assist with your purchase today?"
