#!/usr/bin/env python3
"""Start the MCP server over stdio from this checkout and list its tools.

    uv run python scripts/smoke_mcp.py           # no key needed: start + list tools
    uv run python scripts/smoke_mcp.py --live    # also call morpheus_list_models
                                                 # (uses MORPHEUS_* from your environment)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main(live: bool) -> int:
    params = StdioServerParameters(command=sys.executable, args=["-m", "morpheus_mcp"], env=dict(os.environ))
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = sorted(t.name for t in (await s.list_tools()).tools)
            print("tools:", ", ".join(tools))
            if live:
                res = await s.call_tool("morpheus_list_models", {})
                d = json.loads(res.content[0].text)
                print("morpheus_list_models:", d["status"], f"({len(d.get('models') or [])} models)")
                if d.get("user_alert"):
                    print(d["user_alert"])
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main("--live" in sys.argv)))
