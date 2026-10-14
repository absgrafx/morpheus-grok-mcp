"""Model hierarchy, fallback to the next Morpheus model, host fallback, and alerts (mocked HTTP)."""

import json

import httpx
import pytest

from morpheus_mcp import server
from morpheus_mcp.config import PUBLIC_BASE

ENDPOINT = f"{PUBLIC_BASE}/chat/completions"


def ok_chat(model):
    return httpx.Response(200, json={"id": "x", "choices": [{"message": {"content": f"hi from {model}"},
                                                              "finish_reason": "stop"}]})


def client_for(plan, seen):
    """plan: model -> Response or Exception. seen collects (model) per request."""
    def handler(request: httpx.Request):
        body = json.loads(request.content)
        seen.append(body["model"])
        assert request.headers["authorization"] == "Bearer sk-test0000000000secret"
        r = plan[body["model"]]
        if isinstance(r, Exception):
            raise r
        return r
    return httpx.Client(transport=httpx.MockTransport(handler))


MSG = [{"role": "user", "content": "ping"}]


def test_hierarchy_order_first_model_wins(monkeypatch):
    monkeypatch.setenv("MORPHEUS_MODELS", "a,b,c")
    seen = []
    r = server.do_chat(MSG, client=client_for({"a": ok_chat("a")}, seen))
    assert seen == ["a"]
    assert r["status"] == "ok" and r["model_used"] == "a" and r["content"] == "hi from a"
    assert "alerts" not in r and "user_alert" not in r


def test_explicit_model_goes_first(monkeypatch):
    monkeypatch.setenv("MORPHEUS_MODELS", "a,b")
    seen = []
    r = server.do_chat(MSG, model="b", client=client_for({"b": ok_chat("b")}, seen))
    assert seen == ["b"] and r["model_used"] == "b"


def test_http_error_falls_back_to_next_model_with_alert(monkeypatch):
    monkeypatch.setenv("MORPHEUS_MODELS", "a,b")
    seen = []
    plan = {"a": httpx.Response(502, text="bad gateway"), "b": ok_chat("b")}
    r = server.do_chat(MSG, client=client_for(plan, seen))
    assert seen == ["a", "b"]  # each model once; no silent retry of a
    assert r["status"] == "ok" and r["model_used"] == "b"
    (a,) = r["alerts"]
    assert a["model"] == "a" and a["endpoint"] == ENDPOINT and a["http_status"] == 502
    assert "bad gateway" not in a["error"] and "non-JSON error body" in a["error"] and a["time"] and "next Morpheus model, b" in a["action"]
    assert "Morpheus alert" in r["user_alert"] and "HTTP 502" in r["user_alert"]
    assert "Show the user" in r["agent_instructions"]


def test_timeout_falls_back_to_next_model(monkeypatch):
    monkeypatch.setenv("MORPHEUS_MODELS", "a,b")
    seen = []
    plan = {"a": httpx.ReadTimeout("slow"), "b": ok_chat("b")}
    r = server.do_chat(MSG, timeout_seconds=5, client=client_for(plan, seen))
    assert r["model_used"] == "b"
    (a,) = r["alerts"]
    assert a["http_status"] is None and "timed out after 5s" in a["error"]
    assert "no HTTP response" in r["user_alert"]


def test_empty_response_counts_as_failure(monkeypatch):
    monkeypatch.setenv("MORPHEUS_MODELS", "a,b")
    plan = {"a": httpx.Response(200, json={"choices": []}), "b": ok_chat("b")}
    r = server.do_chat(MSG, client=client_for(plan, []))
    assert r["model_used"] == "b" and "empty response" in r["alerts"][0]["error"]


def test_all_models_fail_returns_control_to_host(monkeypatch):
    monkeypatch.setenv("MORPHEUS_MODELS", "a,b")
    seen = []
    plan = {"a": httpx.Response(500, text="boom"), "b": httpx.ConnectError("refused")}
    r = server.do_chat(MSG, client=client_for(plan, seen))
    assert seen == ["a", "b"]
    assert r["status"] == "host_fallback" and r["use_host_model"] is True
    assert "Use your own model" in r["agent_instructions"]
    assert len(r["alerts"]) == 2
    assert "returned control to the host model" in r["alerts"][-1]["action"]
    assert r["user_alert"].count("Morpheus alert") == 2


def test_auth_error_goes_straight_to_host(monkeypatch):
    monkeypatch.setenv("MORPHEUS_MODELS", "a,b")
    seen = []
    r = server.do_chat(MSG, client=client_for({"a": httpx.Response(401, text="invalid key")}, seen))
    assert seen == ["a"]
    assert r["status"] == "host_fallback" and r["alerts"][0]["http_status"] == 401
    assert "key was rejected" in r["alerts"][0]["action"]


def test_no_model_configured_hands_back_with_alert():
    seen = []
    r = server.do_chat(MSG, client=client_for({}, seen))
    assert seen == []  # nothing was sent to Morpheus
    assert r["status"] == "host_fallback" and r["use_host_model"] is True
    assert "MORPHEUS_MODELS is empty" in r["user_alert"] and len(r["alerts"]) == 1


def test_config_error_hands_back_with_alert(monkeypatch):
    monkeypatch.delenv("MORPHEUS_API_KEY")
    r = server.do_chat(MSG, model="a")
    assert r["status"] == "host_fallback" and "MORPHEUS_API_KEY" in r["user_alert"]


def test_alerts_never_leak_key(monkeypatch):
    monkeypatch.setenv("MORPHEUS_MODELS", "a")
    plan = {"a": httpx.Response(400, text="echo sk-test0000000000secret")}
    r = server.do_chat(MSG, client=client_for(plan, []))
    assert "sk-test0000000000secret" not in json.dumps(r)


def test_alert_is_logged_when_it_happens(monkeypatch, caplog):
    monkeypatch.setenv("MORPHEUS_MODELS", "a,b")
    plan = {"a": httpx.Response(503, text="down"), "b": ok_chat("b")}
    with caplog.at_level("WARNING", logger="morpheus_mcp"):
        server.do_chat(MSG, client=client_for(plan, []))
    assert any("Morpheus alert" in r.message and "HTTP 503" in r.message for r in caplog.records)


def test_embed_fallback(monkeypatch):
    def handler(request):
        m = json.loads(request.content)["model"]
        if m == "e1":
            return httpx.Response(404, text="no such model")
        return httpx.Response(200, json={"data": [{"embedding": [0.1]}], "usage": {}})
    c = httpx.Client(transport=httpx.MockTransport(handler))
    r = server.do_embed("hi", "e1", ["e2"], client=c)
    assert r["model_used"] == "e2" and r["alerts"][0]["http_status"] == 404


def test_list_models_failure_alerts(monkeypatch):
    c = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(502, text="x")))
    r = server.do_list_models(client=c)
    assert r["status"] == "host_fallback" and r["alerts"][0]["http_status"] == 502


def test_list_models_ok(monkeypatch):
    monkeypatch.setenv("MORPHEUS_MODELS", "a")
    c = httpx.Client(transport=httpx.MockTransport(
        lambda req: httpx.Response(200, json={"data": [{"id": "a"}, {"id": "b"}]})))
    r = server.do_list_models(client=c)
    assert r["models"] == ["a", "b"] and r["model_hierarchy"] == ["a"]


@pytest.mark.anyio
async def test_mcp_tools_listed():
    names = {t.name for t in await server.mcp.list_tools()}
    assert names == {"morpheus_chat", "morpheus_embed", "morpheus_list_models"}
