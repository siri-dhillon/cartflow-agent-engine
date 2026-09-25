import os
import asyncio
import json
from dotenv import load_dotenv
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

load_dotenv()

async def test_search():
    endpoint = os.getenv("LOOMI_CONNECT_ENDPOINT")
    auth_token = os.getenv("LOOMI_AUTH_TOKEN", "")

    headers = {}
    if auth_token:
        headers["Authorization"] = auth_token

    print(f"Connecting to: {endpoint}...")
    async with streamablehttp_client(endpoint, headers=headers) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # Execute search_products tool call
            print("\nExecuting tool call: search_products...")
            result = await session.call_tool(
                "search_products",
                arguments={
                    "query": "running shoes"
                }
            )

            print("\n--- Search Results ---")
            for content_block in result.content:
                if hasattr(content_block, "text"):
                    try:
                        # Attempt to pretty print if output is JSON
                        parsed = json.loads(content_block.text)
                        print(json.dumps(parsed, indent=2)[:1500])
                    except Exception:
                        print(content_block.text[:1500])

if __name__ == "__main__":
    asyncio.run(test_search())