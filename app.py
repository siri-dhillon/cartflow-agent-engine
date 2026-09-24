import os
import sys
import asyncio
import json
import streamlit as st

# Ensure root directory is on sys.path for direct python/streamlit execution
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from agent.agent_core import CartFlowAgent

# Set wide page layout titled CartFlow Agent Engine
st.set_page_config(
    page_title="CartFlow Agent Engine",
    page_icon="🛒",
    layout="wide",
)

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

if "telemetry_sink" not in st.session_state:
    st.session_state.telemetry_sink = []

if "agent" not in st.session_state:
    st.session_state.agent = CartFlowAgent()

agent = st.session_state.agent

# Header
st.title("🛒 CartFlow Agent Engine")
st.caption("Autonomous, Margin-Aware E-Commerce Agent Powered by Gemini 1.5, Databricks, Loomi MCP & Shopify")

# 2-column layout (col_chat: 65%, col_inspector: 35%)
col_chat, col_inspector = st.columns([0.65, 0.35], gap="large")

with col_chat:
    st.subheader("💬 Customer Chat Interface")

    # Customer selector at the top (dropdown, default cust_101)
    user_id = st.selectbox(
        "Select Customer Context",
        options=["cust_101", "cust_102", "cust_103"],
        index=0,
        help="cust_101: Gold Tier (15% max discount) | cust_102: Platinum Tier (20% max discount) | cust_103: Silver Tier (10% max discount)",
    )

    # Simulated quick-action prompt buttons for demo convenience
    st.markdown("**Quick Actions:**")
    q_col1, q_col2, q_clear = st.columns([0.45, 0.45, 0.1])
    
    selected_prompt = None
    with q_col1:
        if st.button("🔍 'Find me a waterproof hiking shell'"):
            selected_prompt = "Find me a waterproof hiking shell"
    with q_col2:
        if st.button("🏷️ 'That's great, but $140 is too expensive. Can you do better?'"):
            selected_prompt = "That's great, but $140 is too expensive. Can you do better?"
    with q_clear:
        if st.button("🗑️ Clear"):
            st.session_state.messages = []
            st.session_state.telemetry_sink = []
            st.rerun()

    # Chat history container
    chat_container = st.container(height=480)
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Chat input accepting user queries
    user_input = st.chat_input("Type your request here...")

    prompt_to_send = selected_prompt or user_input

    if prompt_to_send:
        # Record user message in history
        st.session_state.messages.append({"role": "user", "content": prompt_to_send})
        
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt_to_send)

            with st.chat_message("assistant"):
                with st.spinner("CartFlow Agent processing request & invoking integrations..."):
                    # Process message through agent with asyncio.run
                    response_text = asyncio.run(
                        agent.process_message(
                            user_id=user_id,
                            message=prompt_to_send,
                            telemetry_sink=st.session_state.telemetry_sink,
                        )
                    )
                    st.markdown(response_text)
                    st.session_state.messages.append({"role": "assistant", "content": response_text})
        st.rerun()

with col_inspector:
    st.subheader("Multi-Platform Closed-Loop Inspector")

    # Badges showing the 4 active connected systems
    st.markdown(
        """
        <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px;">
            <span style="background-color: #1b365d; color: #ffffff; padding: 5px 12px; border-radius: 14px; font-size: 13px; font-weight: 600;">📊 Databricks</span>
            <span style="background-color: #4285f4; color: #ffffff; padding: 5px 12px; border-radius: 14px; font-size: 13px; font-weight: 600;">✨ Gemini 1.5</span>
            <span style="background-color: #ff5722; color: #ffffff; padding: 5px 12px; border-radius: 14px; font-size: 13px; font-weight: 600;">🌸 Bloomreach Loomi MCP</span>
            <span style="background-color: #96bf48; color: #000000; padding: 5px 12px; border-radius: 14px; font-size: 13px; font-weight: 600;">🛍️ Shopify Storefront</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    # Render chronological cards/expanders for each step in telemetry_sink
    if not st.session_state.telemetry_sink:
        st.info("No integration tool calls logged yet. Send a message to inspect live closed-loop execution telemetry.")
    else:
        st.markdown(f"**Execution Log ({len(st.session_state.telemetry_sink)} events):**")

        for idx, event in enumerate(reversed(st.session_state.telemetry_sink), 1):
            tool_name = event.get("tool", "System Event")
            timestamp = event.get("timestamp", "")
            duration = event.get("duration_ms", 0)

            # Format system label based on tool name
            if tool_name == "get_customer_profile":
                label = f"📊 Databricks Profile Lookup ({duration}ms)"
            elif tool_name == "search_catalog_loomi":
                label = f"🌸 Loomi MCP Search ({duration}ms)"
            elif tool_name == "create_discounted_checkout":
                label = f"🛍️ Shopify Cart Mutation & Databricks Feedback Write-Back ({duration}ms)"
            else:
                label = f"⚙️ {tool_name} ({duration}ms)"

            with st.expander(label, expanded=(idx == 1)):
                st.caption(f"Timestamp: {timestamp}")

                if "arguments" in event:
                    st.markdown("**Arguments:**")
                    st.json(event["arguments"])

                if "result" in event:
                    st.markdown("**Result / Output Payload:**")
                    st.json(event["result"])
