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
                "run_macro",
                arguments={
                    "macro_path": r"C:\Users\Xuan\.codex\mcp\solidworks-mcp\macro\bin\Release\net48\SolidWorksMcpMacro.dll",
                    "module_name": "SolidWorksMcpMacro.EntryPoint",
                    "procedure_name": "Main",
                },
            )

            payload = _payload(result)
            print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))

            if payload.get("reason") != "run_macro_disabled_on_host":
                raise AssertionError(f"Expected safe macro refusal: {json.dumps(payload, ensure_ascii=False)}")


if __name__ == "__main__":
    asyncio.run(main())
