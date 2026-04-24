from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SERVER_PATH = Path(__file__).with_name("server.py")
EXPECTED_TOOLS = {
    "create_rectangular_block",
    "create_plate_with_holes",
    "design_from_prompt",
}


async def main() -> None:
    server_params = StdioServerParameters(command=sys.executable, args=[str(SERVER_PATH)])
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_response = await session.list_tools()
            available = {tool.name for tool in tools_response.tools}
            missing = sorted(EXPECTED_TOOLS - available)
            if missing:
                raise AssertionError(f"Missing expected high-level tools: {missing}")


if __name__ == "__main__":
    asyncio.run(main())
