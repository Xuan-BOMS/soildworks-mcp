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

            steps = [
                ("new_part", {}),
                ("create_sketch_on_plane", {"plane": "front"}),
                (
                    "create_center_rectangle",
                    {
                        "center_x": 0.0,
                        "center_y": 0.0,
                        "corner_x": 0.05,
                        "corner_y": 0.025,
                    },
                ),
                (
                    "add_dimension",
                    {
                        "orientation": "horizontal",
                        "location_x": 0.0,
                        "location_y": 0.04,
                        "segment_index": 0,
                        "method": "direct",
                    },
                ),
            ]

            evidence: dict[str, dict] = {}
            for tool_name, arguments in steps:
                result = await session.call_tool(tool_name, arguments=arguments)
                evidence[tool_name] = _payload(result)

            print(json.dumps(evidence, ensure_ascii=False, indent=2, default=str))

            add_dimension = evidence["add_dimension"]
            if add_dimension.get("ok"):
                raise AssertionError("Expected add_dimension direct mode to be disabled.")
            if add_dimension.get("reason") != "direct_method_disabled":
                raise AssertionError(f"Unexpected add_dimension result: {json.dumps(add_dimension, ensure_ascii=False)}")


if __name__ == "__main__":
    asyncio.run(main())
