"""Served model versus requested model: model_used, requested_model and the model_substituted alert."""

import json

import httpx

from morpheus_mcp import server
from morpheus_mcp.config import PUBLIC_BASE
from morpheus_mcp.fallback import same_model

MSG = [{"role": "user", "content": "ping"}]


def chat_client(served, seen=None):
    def handler(request: httpx.Request):
        body = json.loads(request.content)
        if seen is not None:
            seen.append(body["model"])
        payload = {"id": "x", "choices": [{"message": {"content": "pong"}, "finish_reason": "stop"}]}
        if served is not None:
            payload["model"] = served
        return httpx.Response(200, json=payload)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_exact_match_no_alert():
    r = server.do_chat(MSG, model="deepseek-v4-flash", client=chat_client("deepseek-v4-flash"))
    assert r["status"] == "ok"
    assert r["model_used"] == "deepseek-v4-flash" and r["requested_model"] == "deepseek-v4-flash"
    assert "alerts" not in r and "user_alert" not in r and "served_model" not in r


def test_alias_match_no_alert():
    for requested, served in [("DeepSeek V4 Flash", "deepseek-v4-flash"),
                              ("deepseek_v4_flash", " DeepSeek-V4-Flash "),
                              ("Gemma-4-31b", "google/gemma-4-31b"),
                              ("org/name", "name"),
                              ("BGE-EN-ICL", "text-embedding-bge-en-icl")]:
        assert same_model(requested, served), (requested, served)
        r = server.do_chat(MSG, model=requested, client=chat_client(served))
        assert r["status"] == "ok" and "alerts" not in r
        assert r["model_used"] == served.strip() and r["requested_model"] == requested


def test_substitution_alert_keeps_status_ok():
    assert not same_model("nonexistent-model-xyz", "google-gemma-4-31b-it")
    assert not same_model("flash", "deepseek-v4-flash")  # too short for a prefix alias
    assert not same_model("Gemma-4-31b", "google-gemma-4-31b-it")
    r = server.do_chat(MSG, model="nonexistent-model-xyz", client=chat_client("google-gemma-4-31b-it"))
    assert r["status"] == "ok" and r["content"] == "pong"
    assert r["model_used"] == "google-gemma-4-31b-it" and r["requested_model"] == "nonexistent-model-xyz"
    (a,) = r["alerts"]
    assert a["type"] == "model_substituted"
    assert a["requested"] == "nonexistent-model-xyz" and a["served"] == "google-gemma-4-31b-it"
    assert a["endpoint"] == f"{PUBLIC_BASE}/chat/completions" and a["time"]
    assert "served by google-gemma-4-31b-it" in r["user_alert"]
    assert "use_host_model" not in r


def test_substitution_alert_masks_secrets():
    r = server.do_chat(MSG, model="m", client=chat_client("sk-test0000000000secret"))
    assert "sk-test0000000000secret" not in json.dumps(r)


def test_missing_response_model_falls_back_to_requested():
    r = server.do_chat(MSG, model="a", client=chat_client(None))
    assert r["model_used"] == "a" and r["requested_model"] == "a" and "alerts" not in r


def test_substitution_after_fallback_lists_both_alerts(monkeypatch):
    monkeypatch.setenv("MORPHEUS_MODELS", "a,b")

    def handler(request):
        m = json.loads(request.content)["model"]
        if m == "a":
            return httpx.Response(502, json={"error": {"message": "down"}})
        return httpx.Response(200, json={"model": "other", "choices": [{"message": {"content": "x"}}]})
    r = server.do_chat(MSG, client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert r["status"] == "ok" and r["model_used"] == "other" and r["requested_model"] == "b"
    assert [a.get("type") for a in r["alerts"]] == [None, "model_substituted"]


def embed_client(served):
    def handler(request):
        payload = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}
        if served is not None:
            payload["model"] = served
        return httpx.Response(200, json=payload)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_embed_uses_response_model():
    r = server.do_embed("hello world", "BGE-EN-ICL", client=embed_client("bge-en-icl"))
    assert r["status"] == "ok" and r["model_used"] == "bge-en-icl" and r["requested_model"] == "BGE-EN-ICL"
    assert "alerts" not in r


def test_embed_substitution_alert():
    r = server.do_embed("hello world", "BGE-EN-ICL", client=embed_client("text-embedding-3-small"))
    assert r["status"] == "ok" and r["model_used"] == "text-embedding-3-small"
    assert r["alerts"][0]["type"] == "model_substituted"
    assert r["alerts"][0]["endpoint"] == f"{PUBLIC_BASE}/embeddings"


def test_embed_missing_response_model():
    r = server.do_embed("hello world", "BGE-EN-ICL", client=embed_client(None))
    assert r["model_used"] == "BGE-EN-ICL" and r["requested_model"] == "BGE-EN-ICL"
