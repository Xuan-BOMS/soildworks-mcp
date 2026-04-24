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

            prompt = (
                "Create a 100 mm by 60 mm by 5 mm rectangular plate with 4 through holes "
                "of diameter 3 mm in a 2 by 2 grid, each hole center 10 mm from the nearest edges."
            )
            result = await session.call_tool("design_from_prompt", arguments={"prompt": prompt})
            payload = _payload(result)
            print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
            if not payload.get("ok"):
                raise AssertionError(f"design_from_prompt failed: {json.dumps(payload, ensure_ascii=False)}")
            if payload.get("shape") != "plate_with_holes":
                raise AssertionError(f"Unexpected shape: {json.dumps(payload, ensure_ascii=False)}")


if __name__ == "__main__":
    asyncio.run(main())
