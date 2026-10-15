"""End to end over stdio: server starts, lists tools, and sends alerts as MCP log messages."""

import json
import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from morpheus_mcp import __version__


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
            init = await s.initialize()
            assert init.serverInfo.name == "morpheus-inference"
            assert init.serverInfo.version == __version__ == "0.2.2"
            tools = {t.name: t for t in (await s.list_tools()).tools}
            assert set(tools) == {"morpheus_chat", "morpheus_embed", "morpheus_list_models"}
            assert "ctx" not in tools["morpheus_chat"].inputSchema["properties"]
            res = await s.call_tool("morpheus_chat", {"messages": [{"role": "user", "content": "hi"}]})
            d = json.loads(res.content[0].text)
    assert d["status"] == "host_fallback" and [a["model"] for a in d["alerts"]] == ["m1", "m2"]
    assert logs and logs[0].level == "warning" and "Morpheus alert" in str(logs[0].data)
    assert "sk-fake0000000000" not in json.dumps(d)


@pytest.mark.anyio
async def test_stdio_500_echo_never_reaches_mcp_log_or_stderr(tmp_path):
    """Real server process + real local HTTP 500 that echoes the key and the prompt."""
    import http.server
    import threading

    key, prompt = "ukey_STDIO_SECRET_9876", "TOPSECRET stdio prompt text for the gate"

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            self.rfile.read(int(self.headers.get("content-length", 0)))
            body = json.dumps({"error": {"message": f"{key} {prompt}", "type": "server_error"}}).encode()
            self.send_response(500)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    logs = []

    async def on_log(params):
        logs.append(str(params.data))

    env = dict(os.environ, MORPHEUS_MODE="uplink", MORPHEUS_BASE_URL=f"http://127.0.0.1:{srv.server_port}/v1",
               MORPHEUS_MODELS="m1", MORPHEUS_API_KEY=key)
    errfile = tmp_path / "stderr.txt"
    try:
        with errfile.open("w") as errlog:
            params = StdioServerParameters(command=sys.executable, args=["-m", "morpheus_mcp", "--verbose"], env=env)
            async with stdio_client(params, errlog=errlog) as (r, w):
                async with ClientSession(r, w, logging_callback=on_log) as s:
                    await s.initialize()
                    res = await s.call_tool("morpheus_chat", {"messages": [{"role": "user", "content": prompt}]})
                    text = res.content[0].text
    finally:
        srv.shutdown()
    stderr = errfile.read_text()
    assert json.loads(text)["status"] == "host_fallback" and logs and "Morpheus alert" in stderr
    for blob in (text, stderr, *logs):
        assert key not in blob and "TOPSECRET" not in blob
