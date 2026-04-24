from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SERVER_PATH = Path(__file__).with_name("server.py")
REQUIRED_TOOLS = [
    "new_part",
    "create_sketch_on_plane",
    "create_center_rectangle",
    "create_circle",
    "add_dimension",
    "extrude_boss",
    "run_macro",
    "create_rectangular_block",
    "create_plate_with_holes",
    "design_from_prompt",
]


async def main() -> None:
    server_params = StdioServerParameters(command=sys.executable, args=[str(SERVER_PATH)])
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = sorted(tool.name for tool in tools.tools)
            missing = [name for name in REQUIRED_TOOLS if name not in names]
            if missing:
                raise AssertionError(
                    "Missing required tools: "
                    + ", ".join(missing)
                    + "\nAvailable: "
                    + json.dumps(names, ensure_ascii=False)
                )


if __name__ == "__main__":
    asyncio.run(main())
