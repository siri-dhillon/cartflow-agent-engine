"""
Retention & Risk Agent.

Specialized agent connected to Databricks MCP server (Unity Catalog & Model Serving).
Evaluates customer LTV, churn risk score, and computes margin-safe dynamic discount authorization caps.
"""

from typing import Dict, Any, Optional
from ..protocols.a2a_schema import (
    A2AMessage,
    TaskRequest,
    Artifacts,
    RiskAssessment,
    DiscountOffer,
    AgentID,
    PerformativeEnum,
)
from ..mcp_servers.databricks_server import DatabricksMCPServer


class RetentionAgent:
    """
    Retention Agent responsible for dynamic margin-safe discount generation and churn prevention.
    """

    def __init__(self, databricks_server: Optional[DatabricksMCPServer] = None):
        self.agent_id = AgentID.RETENTION
        self.databricks_server = databricks_server or DatabricksMCPServer()

    async def handle_message(self, message: A2AMessage) -> A2AMessage:
        """
        Process incoming A2A message requests for customer risk evaluation and retention offers.
        """
        if message.performative not in (PerformativeEnum.REQUEST, PerformativeEnum.PROPOSE):
            return A2AMessage(
                conversation_id=message.conversation_id,
                sender=self.agent_id,
                receiver=message.sender,
                performative=PerformativeEnum.REJECT,
                content="Retention Agent accepts REQUEST or PROPOSE performatives.",
            )

        task = message.task or TaskRequest(
            goal="Retention Risk & Discount Assessment",
            customer_id="cust_101",
        )

        customer_id = task.customer_id or "cust_101"
        hesitation_signal = task.metadata.get("hesitation_detected", True)
        requested_discount = float(task.metadata.get("requested_discount_pct", 15.0))
        cart_value = float(task.metadata.get("cart_value", 180.00))

        # 1. Evaluate real-time churn risk via Databricks MCP
        risk_res = await self.databricks_server.databricks_evaluate_churn_risk(
            customer_id=customer_id,
            hesitation_signal=hesitation_signal,
            cart_value=cart_value,
        )

        # 2. Enforce margin guardrails to calculate approved discount
        disc_res = await self.databricks_server.databricks_calculate_max_discount(
            customer_id=customer_id,
            requested_discount_pct=requested_discount,
        )

        # Build risk assessment model
        risk_model = RiskAssessment(
            customer_id=customer_id,
            loyalty_tier=risk_res.get("loyalty_tier", "STANDARD"),
            churn_risk_score=risk_res.get("churn_risk_score", 0.5),
            risk_level=risk_res.get("risk_level", "MEDIUM"),
            hesitation_detected=hesitation_signal,
            max_authorized_discount_pct=disc_res.get("max_authorized_pct", 10.0),
        )

        # Build discount offer model
        approved_pct = disc_res.get("approved_discount_pct", 10.0)
        discount_offer = DiscountOffer(
            discount_code=disc_res.get("discount_code", "SAVE10"),
            discount_pct=approved_pct,
            max_authorized_pct=disc_res.get("max_authorized_pct", 10.0),
            applied=True,
            reason=f"Loyalty retention incentive for {risk_model.loyalty_tier} tier shopper.",
        )

        content_msg = (
            f"Authorized {approved_pct}% dynamic discount code '{discount_offer.discount_code}' "
            f"for customer '{customer_id}' ({risk_model.loyalty_tier} tier, {risk_model.risk_level} churn risk)."
        )

        return A2AMessage(
            conversation_id=message.conversation_id,
            sender=self.agent_id,
            receiver=message.sender,
            performative=PerformativeEnum.PROPOSE,
            content=content_msg,
            task=task,
            artifacts=Artifacts(
                risk_assessment=risk_model,
                discount_offer=discount_offer,
            ),
        )
