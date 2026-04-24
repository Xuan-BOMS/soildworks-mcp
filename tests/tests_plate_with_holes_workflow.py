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
                "create_plate_with_holes",
                arguments={
                    "width_mm": 100.0,
                    "height_mm": 60.0,
                    "thickness_mm": 5.0,
                    "hole_diameter_mm": 3.0,
                    "offset_x_mm": 10.0,
                    "offset_y_mm": 10.0,
                    "rows": 2,
                    "columns": 2,
                },
            )
            payload = _payload(result)
            print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
            if not payload.get("ok"):
                raise AssertionError(f"create_plate_with_holes failed: {json.dumps(payload, ensure_ascii=False)}")

            if payload.get("holeCount") != 4:
                raise AssertionError(f"Expected 4 holes, got {payload.get('holeCount')}")


if __name__ == "__main__":
    asyncio.run(main())
