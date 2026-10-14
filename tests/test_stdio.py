"""End to end over stdio: server starts, lists tools, and sends alerts as MCP log messages."""

import json
import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.anyio
async def test_stdio_tools_and_alert_log_messages():
    logs = []

    async def on_log(params):
        logs.append(params)

    env = dict(os.environ, MORPHEUS_MODE="uplink", MORPHEUS_BASE_URL="http://127.0.0.1:9/v1",
               MORPHEUS_MODELS="m1,m2", MORPHEUS_API_KEY="sk-fake0000000000")
    params = StdioServerParameters(command=sys.executable, args=["-m", "morpheus_mcp"], env=env)
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w, logging_callback=on_log) as s:
            await s.initialize()
            tools = {t.name: t for t in (await s.list_tools()).tools}
            assert set(tools) == {"morpheus_chat", "morpheus_embed", "morpheus_list_models"}
            assert "ctx" not in tools["morpheus_chat"].inputSchema["properties"]
            res = await s.call_tool("morpheus_chat", {"messages": [{"role": "user", "content": "hi"}]})
            d = json.loads(res.content[0].text)
    assert d["status"] == "host_fallback" and [a["model"] for a in d["alerts"]] == ["m1", "m2"]
    assert logs and logs[0].level == "warning" and "Morpheus alert" in str(logs[0].data)
    assert "sk-fake0000000000" not in json.dumps(d)
