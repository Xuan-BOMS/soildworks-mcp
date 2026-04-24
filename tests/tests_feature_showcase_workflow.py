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
                "create_feature_showcase_part",
                arguments={
                    "base_width_mm": 120.0,
                    "base_height_mm": 80.0,
                    "base_thickness_mm": 12.0,
                    "hole_diameter_mm": 6.0,
                    "hole_offset_mm": 15.0,
                    "rows": 2,
                    "columns": 2,
                    "boss_width_mm": 50.0,
                    "boss_height_mm": 30.0,
                    "boss_thickness_mm": 8.0,
                    "boss_offset_x_mm": 18.0,
                    "boss_offset_y_mm": 0.0,
                    "fillet_radius_mm": 3.0,
                    "chamfer_distance_mm": 2.0,
                },
            )
            payload = _payload(result)
            print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
            if not payload.get("ok"):
                raise AssertionError(f"create_feature_showcase_part failed: {json.dumps(payload, ensure_ascii=False)}")

            inspection = payload.get("inspection", {})
            if not inspection.get("ok"):
                raise AssertionError(f"Inspection missing or failed: {json.dumps(payload, ensure_ascii=False)}")

            feature_types = {feature.get("canonicalType", feature["typeName"]) for feature in inspection.get("features", [])}
            required_types = {"Boss", "Cut", "Fillet", "Chamfer"}
            missing = sorted(required_types - feature_types)
            if missing:
                raise AssertionError(
                    f"Showcase part is missing feature types {missing}: {json.dumps(inspection, ensure_ascii=False)}"
                )

            validation = payload.get("validation", {})
            if not all(
                validation.get(key)
                for key in ["bossValidated", "cutValidated", "filletValidated", "chamferValidated"]
            ):
                raise AssertionError(f"Showcase validation is incomplete: {json.dumps(payload, ensure_ascii=False)}")

            combine_result = payload.get("steps", {}).get("combine_all_bodies", {})
            if validation.get("combineValidated"):
                if inspection.get("bodyCount") != 1:
                    raise AssertionError(f"Expected a single combined body: {json.dumps(inspection, ensure_ascii=False)}")
                if "Combine" not in feature_types:
                    raise AssertionError(f"Expected Combine feature in inspection: {json.dumps(inspection, ensure_ascii=False)}")
            else:
                if combine_result.get("reason") != "combine_insert_failed":
                    raise AssertionError(f"Unexpected combine status: {json.dumps(payload, ensure_ascii=False)}")
                if inspection.get("bodyCount") < 2:
                    raise AssertionError(
                        f"Expected multibody fallback evidence when combine is unavailable: {json.dumps(inspection, ensure_ascii=False)}"
                    )


if __name__ == "__main__":
    asyncio.run(main())
