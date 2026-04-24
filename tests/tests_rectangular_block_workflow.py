from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SERVER_PATH = Path(__file__).with_name("server.py")


def _payload(result) -> dict:
    if hasattr(result, "structuredContent"):
        return result.structuredContent or {}
    return getattr(result, "structured_content", {}) or {}


async def main() -> None:
    server_params = StdioServerParameters(command=sys.executable, args=[str(SERVER_PATH)])
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool(
                "create_rectangular_block",
                arguments={
                    "width_mm": 100.0,
                    "height_mm": 50.0,
                    "depth_mm": 10.0,
                },
            )
            payload = _payload(result)
            print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
            if not payload.get("ok"):
                raise AssertionError(f"create_rectangular_block failed: {json.dumps(payload, ensure_ascii=False)}")


if __name__ == "__main__":
    asyncio.run(main())
