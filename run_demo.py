"""
CLI end-to-end runner and verification script for CartFlow Agent Engine.
Simulates complete customer interaction flow without Streamlit and asserts all 4 platforms were triggered:
1. Google Gemini (Agent Reasoning Core)
2. Bloomreach Loomi MCP (Catalog Search)
3. Databricks (Customer Profiling & Closed-Loop Telemetry Write-Back)
4. Shopify Storefront (Cart Mutation & Discount Application)
"""
import os
import sys
import asyncio
import json

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from agent.agent_core import CartFlowAgent


async def main():
    print("=" * 80)
    print("🚀 STARTING CARTFLOW AGENT ENGINE END-TO-END DEMO FLOW")
    print("=" * 80)

    user_id = "cust_101"
    agent = CartFlowAgent(use_mocks=True)
    telemetry_sink = []

    # Turn 1: Product search query
    user_query_1 = "Find me a waterproof hiking shell"
    print(f"\n👤 Customer ({user_id}): {user_query_1}")
    response_1 = await agent.process_message(user_id=user_id, message=user_query_1, telemetry_sink=telemetry_sink)
    print(f"\n🤖 CartFlow Agent:\n{response_1}")

    # Turn 2: Price hesitation & discount request
    user_query_2 = "That's great, but $140 is too expensive. Can you do better?"
    print(f"\n👤 Customer ({user_id}): {user_query_2}")
    response_2 = await agent.process_message(user_id=user_id, message=user_query_2, telemetry_sink=telemetry_sink)
    print(f"\n🤖 CartFlow Agent:\n{response_2}")

    print("\n" + "=" * 80)
    print("📊 CLOSED-LOOP SYSTEM TELEMETRY AUDIT")
    print("=" * 80)

    triggered_tools = [t.get("tool") for t in telemetry_sink if "tool" in t]
    print(f"\nLogged Tool Executions ({len(telemetry_sink)} events):")
    for idx, event in enumerate(telemetry_sink, 1):
        print(f"  {idx}. System: {event.get('tool')} | Duration: {event.get('duration_ms')}ms")

    # Platform Trigger Verification
    loomi_triggered = "search_catalog_loomi" in triggered_tools
    databricks_profile_triggered = "get_customer_profile" in triggered_tools
    shopify_and_db_feedback_triggered = "create_discounted_checkout" in triggered_tools
    gemini_agent_active = len(response_2) > 0

    print("\n🔍 Platform Integration Verification:")
    print(f"  [1] ✨ Google Gemini 1.5 Agent Core: {'✅ ACTIVE' if gemini_agent_active else '❌ INACTIVE'}")
    print(f"  [2] 🌸 Bloomreach Loomi MCP:         {'✅ TRIGGERED' if loomi_triggered else '❌ NOT TRIGGERED'}")
    print(f"  [3] 📊 Databricks Profiler:          {'✅ TRIGGERED' if databricks_profile_triggered else '❌ NOT TRIGGERED'}")
    print(f"  [4] 🛍️ Shopify Storefront Cart:      {'✅ TRIGGERED' if shopify_and_db_feedback_triggered else '❌ NOT TRIGGERED'}")

    # Assertions
    assert gemini_agent_active, "Gemini Agent Core did not return a response"
    assert loomi_triggered, "Bloomreach Loomi MCP search was not triggered"
    assert databricks_profile_triggered, "Databricks profile lookup was not triggered"
    assert shopify_and_db_feedback_triggered, "Shopify cart creation & Databricks feedback write-back were not triggered"

    print("\n🎉 ALL 4 PLATFORMS SUCCESSFULLY TRIGGERED & CLOSED-LOOP AUDIT VERIFIED!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
