from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = REPO_ROOT / "server.py"


def payload(result) -> dict:
    if hasattr(result, "structuredContent"):
        return result.structuredContent or {}
    return getattr(result, "structured_content", {}) or {}


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER_PATH)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            ping_result = payload(await session.call_tool("ping", arguments={}))
            status_result = payload(await session.call_tool("solidworks_status", arguments={}))

            print("PING", json.dumps(ping_result, ensure_ascii=False, indent=2, default=str))
            print("STATUS", json.dumps(status_result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
