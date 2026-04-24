from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SERVER_PATH = Path(__file__).with_name("server.py")


async def main() -> None:
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("TOOLS", json.dumps([tool.name for tool in tools.tools], ensure_ascii=False))

            for tool_name in ("ping", "solidworks_status", "launch_solidworks", "active_document"):
                result = await session.call_tool(tool_name, arguments={})
                payload = result.structuredContent if hasattr(result, "structuredContent") else result.structured_content
                print(tool_name.upper(), json.dumps(payload, ensure_ascii=False, default=str))

            close_result = await session.call_tool("close_solidworks", arguments={})
            close_payload = close_result.structuredContent if hasattr(close_result, "structuredContent") else close_result.structured_content
            print("CLOSE_SOLIDWORKS", json.dumps(close_payload, ensure_ascii=False, default=str))


if __name__ == "__main__":
    asyncio.run(main())
