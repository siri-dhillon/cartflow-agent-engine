"""
Agent-to-Agent (A2A) Orchestrator Bus.

Asynchronous event bus and workflow orchestrator executing multi-agent conversion flows
across Concierge, Discovery, Retention, and Checkout agents.
"""

from typing import Dict, Any, List, Optional
import logging
import uuid

from .protocols.a2a_schema import (
    A2AMessage,
    TaskRequest,
    Artifacts,
    AgentID,
    PerformativeEnum,
)
from .agents.concierge_agent import ConciergeAgent
from .agents.discovery_agent import DiscoveryAgent
from .agents.retention_agent import RetentionAgent
from .agents.checkout_agent import CheckoutAgent

logger = logging.getLogger("cartflow.orchestrator")


class A2AOrchestrator:
    """
    Agent-to-Agent Async Message Bus & Multi-Agent Workflow Engine.
    """

    def __init__(
        self,
        concierge: Optional[ConciergeAgent] = None,
        discovery: Optional[DiscoveryAgent] = None,
        retention: Optional[RetentionAgent] = None,
        checkout: Optional[CheckoutAgent] = None,
    ):
        self.concierge = concierge or ConciergeAgent()
        self.discovery = discovery or DiscoveryAgent()
        self.retention = retention or RetentionAgent()
        self.checkout = checkout or CheckoutAgent()

        self.agents: Dict[AgentID, Any] = {
            AgentID.CONCIERGE: self.concierge,
            AgentID.DISCOVERY: self.discovery,
            AgentID.RETENTION: self.retention,
            AgentID.CHECKOUT: self.checkout,
        }

        self.message_history: List[A2AMessage] = []

    async def send_message(self, message: A2AMessage) -> A2AMessage:
        """
        Deliver an A2AMessage to the intended recipient agent and log telemetry.
        """
        self.message_history.append(message)
        target_agent = self.agents.get(message.receiver)

        if not target_agent:
            err_msg = A2AMessage(
                conversation_id=message.conversation_id,
                sender=AgentID.CONCIERGE,
                receiver=message.sender,
                performative=PerformativeEnum.FAILURE,
                content=f"Agent '{message.receiver}' is not registered on A2A bus.",
            )
            self.message_history.append(err_msg)
            return err_msg

        if hasattr(target_agent, "handle_message"):
            response_msg = await target_agent.handle_message(message)
            self.message_history.append(response_msg)
            return response_msg

        return message

    async def process_customer_journey(
        self,
        customer_id: str,
        user_message: str,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute end-to-end multi-agent customer conversion flow.
        """
        conv_id = conversation_id or f"conv_{uuid.uuid4().hex[:8]}"
        intent = self.concierge.classify_intent(user_message)

        collected_artifacts = Artifacts()

        # Step 1: Product Discovery (if applicable)
        msg_disc = A2AMessage(
            conversation_id=conv_id,
            sender=AgentID.CONCIERGE,
            receiver=AgentID.DISCOVERY,
            performative=PerformativeEnum.REQUEST,
            content=user_message,
            task=TaskRequest(
                goal="Catalog Product Search",
                customer_id=customer_id,
                query=user_message,
            ),
        )
        res_disc = await self.send_message(msg_disc)
        if res_disc.artifacts and res_disc.artifacts.recommendations:
            collected_artifacts.recommendations = res_disc.artifacts.recommendations

        # Step 2: Handle Price Hesitation & Dynamic Discounting (Retention Agent)
        if intent == "HESITATION":
            top_price = 180.00
            if collected_artifacts.recommendations:
                top_price = collected_artifacts.recommendations[0].price

            msg_ret = A2AMessage(
                conversation_id=conv_id,
                sender=AgentID.CONCIERGE,
                receiver=AgentID.RETENTION,
                performative=PerformativeEnum.REQUEST,
                content=f"Customer hesitating on price (${top_price:.2f}). Evaluate churn risk and discount cap.",
                task=TaskRequest(
                    goal="Evaluate Churn & Dynamic Discount",
                    customer_id=customer_id,
                    metadata={
                        "hesitation_detected": True,
                        "requested_discount_pct": 15.0,
                        "cart_value": top_price,
                    },
                ),
            )
            res_ret = await self.send_message(msg_ret)
            if res_ret.artifacts:
                collected_artifacts.risk_assessment = res_ret.artifacts.risk_assessment
                collected_artifacts.discount_offer = res_ret.artifacts.discount_offer

        # Step 3: Cart Creation & 1-Click Checkout URL (Checkout Agent)
        if intent in ("HESITATION", "CHECKOUT"):
            variant_id = "gid://shopify/ProductVariant/v_run_01_m"
            price = 180.00
            if collected_artifacts.recommendations:
                variant_id = collected_artifacts.recommendations[0].variant_id
                price = collected_artifacts.recommendations[0].price

            msg_chk = A2AMessage(
                conversation_id=conv_id,
                sender=AgentID.CONCIERGE,
                receiver=AgentID.CHECKOUT,
                performative=PerformativeEnum.REQUEST,
                content="Create cart and generate 1-click checkout URL.",
                task=TaskRequest(
                    goal="Assemble Cart and Checkout Link",
                    customer_id=customer_id,
                    cart_items=[{"variant_id": variant_id, "quantity": 1, "price": price}],
                    discount_code=collected_artifacts.discount_offer.discount_code if collected_artifacts.discount_offer else None,
                ),
                artifacts=collected_artifacts,
            )
            res_chk = await self.send_message(msg_chk)
            if res_chk.artifacts and res_chk.artifacts.checkout_details:
                collected_artifacts.checkout_details = res_chk.artifacts.checkout_details

        # Step 4: Concierge Synthesis
        final_response_text = await self.concierge.generate_response(
            user_message=user_message,
            artifacts=collected_artifacts,
            customer_id=customer_id,
        )

        return {
            "conversation_id": conv_id,
            "customer_id": customer_id,
            "intent": intent,
            "response": final_response_text,
            "artifacts": collected_artifacts.model_dump(),
            "telemetry_count": len(self.message_history),
        }
