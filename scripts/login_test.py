import asyncio
import sys
import traceback
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

CATALOG_TEST_URL = "https://orgfarm-6e1a6e3ea8-dev-ed.develop.lightning.force.com/lightning/n/Catalog_Test"

server_params = StdioServerParameters(command="npx", args=["playwright-mcp-server"])

async def main():
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("Navigating...", flush=True)
                result = await session.call_tool(
                    "playwright_navigate",
                    {"url": CATALOG_TEST_URL, "headless": False}
                )
                print("Navigate result:", result, flush=True)
                print("\nBrowser window should now be open.", flush=True)
                print("If it shows a Salesforce login page, LOG IN NOW manually.", flush=True)
                print("You have 10 MINUTES before this script exits.\n", flush=True)

                for remaining in range(600, 0, -10):
                    print(f"  ...{remaining} seconds left", flush=True)
                    await asyncio.sleep(10)

                print("Time's up, closing.", flush=True)
    except Exception:
        print("\n\n=== EXCEPTION OCCURRED ===", flush=True)
        traceback.print_exc()
        print("=== END EXCEPTION ===\n", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
