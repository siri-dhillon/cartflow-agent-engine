# CartFlow Agent Engine

> **Autonomous, Margin-Aware Conversational Commerce & Closed-Loop Checkout Assistant**

---

## 🏆 Hackathon Overview

* **Project Name**: `cartflow-agent-engine`
* **Hackathon Track**: **Track T2 — Conversational Commerce & Checkout Agents**
* **System Integration Level**: **4-System "Strong" Closed-Loop Tier**

### 🧩 Connected Platforms & Systems:
1. **🌸 Bloomreach Loomi MCP**: Product catalog discovery, intelligent search, and contextual merchandise recommendations via MCP SSE connection.
2. **✨ Google Gemini 1.5 Flash**: Autonomous reasoning core enforcing system instructions, price resistance handling, and multi-turn function calling.
3. **📊 Databricks**: Customer profiling (loyalty tier, churn risk evaluation, allowable discount limits) and real-time transaction telemetry write-back.
4. **🛍️ Shopify Storefront API**: Dynamic cart creation, automated discount code application, and 1-click checkout URL generation.

---

## 🔄 Closed Feedback Loop Architecture

```
                       ┌────────────────────────┐
                       │  Bloomreach Loomi MCP  │
                       │    Catalog Search      │
                       └───────────┬────────────┘
                                   │
                                   ▼
┌─────────────────┐     ┌──────────────────────┐     ┌──────────────────┐
│   Databricks    │────>│  Google Gemini 1.5   │────>│     Shopify      │
│ Customer Profile│     │  CartFlow Agent Core │     │ Storefront Cart  │
└────────┬────────┘     └──────────────────────┘     └─────────┬────────┘
         ▲                                                     │
         │           Closed-Loop Write-Back Telemetry          │
         └─────────────────────────────────────────────────────┘
```

### How the Closed Loop Works:
1. **Customer Context Query**: When a customer (e.g. `cust_101`) exhibits price hesitation, CartFlow Agent queries **Databricks** to retrieve their loyalty tier (e.g. `Gold`) and maximum authorized discount margin (`15%`).
2. **Margin Protection**: CartFlow Agent ensures no discount ever exceeds `max_authorized_discount_pct`, protecting merchant margins while maximizing conversion probability.
3. **Cart & Discount Execution**: The agent invokes **Shopify Storefront API** to create a cart and apply the dynamic discount code (`GOLD15`).
4. **Telemetry Write-Back & Loop Closure**: Immediately upon cart creation, the transaction details (order value, discount applied) are written back to **Databricks**, updating the customer's LTV and lowering their churn risk score in real time.

---

## ⚡ Quick Start & Setup Instructions

### Prerequisites
- Python 3.10+
- `pip` package manager

### 1. Environment Setup
```bash
cd cartflow-agent-engine

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# macOS/Linux:
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env` and fill in your API credentials (or use `USE_MOCKS=True` for offline testing):
```bash
cp .env.example .env
```

```env
GEMINI_API_KEY=your_gemini_api_key_here
LOOMI_CONNECT_ENDPOINT=https://example.com/loomi/sse
LOOMI_AUTH_TOKEN=your_loomi_auth_token_here
SHOPIFY_STORE_DOMAIN=your-store.myshopify.com
SHOPIFY_STOREFRONT_TOKEN=your_shopify_storefront_token_here
DATABRICKS_HOST=https://your-databricks-instance.cloud.databricks.com
USE_MOCKS=True
```

### 4. Run Command-Line E2E Verification
Verify the end-to-end integration flow and platform assertions without Streamlit:
```bash
python run_demo.py
```

### 5. Launch Interactive Streamlit Demo App
```bash
streamlit run app.py
```

---

## 🎬 Complete 2-Minute Video Recording Script

### **Title**: CartFlow Agent Engine — Margin-Aware Conversational Commerce
**Speaker**: Presenter / Developer  
**Total Duration**: 2 Minutes (120 Seconds)

---

### ⏱️ Timestamped Script & Screen Click Path

| Timestamp | Phase / Screen | Actions & Visual Click Path | Voiceover Script |
| :--- | :--- | :--- | :--- |
| **0:00 - 0:15** | **Introduction & Architecture** | Full-screen view of `app.py`. Highlight the 4 system badges in the right inspector column: Databricks, Gemini 1.5, Loomi MCP, Shopify. | *"Welcome to CartFlow Agent Engine, an autonomous conversational commerce assistant competing in Track T2. We connect 4 enterprise platforms—Bloomreach Loomi MCP, Google Gemini, Shopify, and Databricks—to create a margin-aware, closed-loop checkout experience."* |
| **0:15 - 0:45** | **Catalog Search & Intent Discovery** | Select `cust_101` in dropdown. Click quick action button: `🔍 Find me a waterproof hiking shell`. Point to the Loomi MCP search card opening in the right column inspector. | *"First, customer cust_101 asks for product recommendations. Gemini 1.5 autonomously invokes Bloomreach Loomi MCP via tool calling to search the catalog and returns the Aura Flow Eco Smart Shell."* |
| **0:45 - 1:15** | **Price Hesitation & Databricks Margin Lookup** | Click quick action button: `🏷️ That's great, but $140 is too expensive. Can you do better?`. Show Databricks Profile Lookup expander card appearing in the inspector. | *"When the user hesitates on price, CartFlow Agent queries Databricks for cust_101's profile. Databricks reveals a Gold tier status with a 15% maximum authorized discount margin."* |
| **1:15 - 1:45** | **Shopify Cart Mutation & Closed-Loop Write-Back** | Show the assistant's final response with 1-click checkout link. Expand the `Shopify Cart Mutation & Databricks Feedback Write-Back` card in the inspector. Highlight `final_price` and `updated_ltv`. | *"The agent applies a 15% discount code GOLD15 via Shopify Storefront GraphQL and generates a 1-click checkout URL. Simultaneously, it writes transaction metrics back to Databricks, updating LTV and reducing churn risk to close the feedback loop."* |
| **1:45 - 2:00** | **Conclusion & CLI Verification** | Switch briefly to terminal window showing `python run_demo.py` with 4 `✅ TRIGGERED` assertions passed. | *"In summary, CartFlow Agent protects merchant margins while driving frictionless conversions across all four platforms. Thank you!"* |
