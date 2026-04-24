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

            calls = [
                ("new_part", {}),
                ("create_sketch_on_plane", {"plane": "front"}),
                (
                    "create_center_rectangle",
                    {
                        "center_x": 0.0,
                        "center_y": 0.0,
                        "corner_x": 0.05,
                        "corner_y": 0.03,
                    },
                ),
                ("extrude_boss", {"depth": 0.01}),
                ("create_sketch_on_plane", {"plane": "front"}),
                ("create_circle", {"center_x": 0.0, "center_y": 0.0, "radius": 0.005}),
                ("extrude_cut", {"depth": 0.02, "through_all": True}),
                ("inspect_active_part", {}),
            ]

            evidence: dict[str, dict] = {}
            for tool_name, arguments in calls:
                result = await session.call_tool(tool_name, arguments=arguments)
                evidence[tool_name] = _payload(result)

            print(json.dumps(evidence, ensure_ascii=False, indent=2, default=str))

            cut_result = evidence["extrude_cut"]
            if not cut_result.get("ok"):
                raise AssertionError(f"extrude_cut failed: {json.dumps(cut_result, ensure_ascii=False)}")

            inspection = evidence["inspect_active_part"]
            if not inspection.get("ok"):
                raise AssertionError(f"inspect_active_part failed: {json.dumps(inspection, ensure_ascii=False)}")

            feature_types = {feature.get("canonicalType", feature["typeName"]) for feature in inspection.get("features", [])}
            if "Cut" not in feature_types:
                raise AssertionError(f"Expected Cut feature in inspection: {json.dumps(inspection, ensure_ascii=False)}")


if __name__ == "__main__":
    asyncio.run(main())
