"""Gate items: no raw upstream body, key or prompt in alerts/logs; base URL rules; timeout clamp."""

import json
import logging

import httpx
import pytest

from morpheus_mcp import server
from morpheus_mcp.config import ConfigError, load_config, normalize_uplink_base
from morpheus_mcp.http_client import clamp_timeout

KEY = "ukey_SECRETVALUE_not_sk_format_42"
PROMPT = "TOPSECRET project codename bluebird launch plan"


@pytest.fixture
def uplink(monkeypatch):
    monkeypatch.setenv("MORPHEUS_MODE", "uplink")
    monkeypatch.setenv("MORPHEUS_BASE_URL", "https://uplink.example.com/v1")
    monkeypatch.setenv("MORPHEUS_API_KEY", KEY)
    monkeypatch.setenv("MORPHEUS_MODELS", "a,b")


def run_chat(handler, caplog):
    c = httpx.Client(transport=httpx.MockTransport(handler))
    with caplog.at_level(logging.INFO, logger="morpheus_mcp"):
        r = server.do_chat([{"role": "user", "content": PROMPT}], client=c)
    return json.dumps(r), r, caplog.text


def assert_clean(*texts):
    for t in texts:
        assert KEY not in t
        assert "TOPSECRET" not in t and "bluebird" not in t


def test_500_echoing_key_and_prompt_json(uplink, caplog):
    def h(req):
        body = {"error": {"message": f"bad key {KEY} for prompt {PROMPT}", "type": "server_error"}}
        return httpx.Response(500, json=body)
    blob, r, logs = run_chat(h, caplog)
    assert r["status"] == "host_fallback"
    assert_clean(blob, logs, r["user_alert"])
    assert "server_error" in r["alerts"][0]["error"]
    assert "withheld" in r["alerts"][0]["error"]


def test_500_echoing_key_only_is_parsed_and_redacted(uplink, caplog):
    h = lambda req: httpx.Response(500, json={"detail": f"internal failure, key {KEY} rejected"})  # noqa: E731
    blob, r, logs = run_chat(h, caplog)
    assert_clean(blob, logs)
    assert "internal failure" in r["alerts"][0]["error"] and "[redacted]" in r["alerts"][0]["error"]


def test_500_raw_text_body_never_shown(uplink, caplog):
    h = lambda req: httpx.Response(500, text=f"Traceback ... {KEY} ... {PROMPT}")  # noqa: E731
    blob, r, logs = run_chat(h, caplog)
    assert_clean(blob, logs)
    assert "non-JSON error body" in r["alerts"][0]["error"]


def test_error_message_is_capped(uplink, caplog):
    h = lambda req: httpx.Response(500, json={"error": {"message": "x" * 5000, "type": "t" * 500}})  # noqa: E731
    _, r, _ = run_chat(h, caplog)
    assert len(r["alerts"][0]["error"]) < 300


def test_transport_error_redacts_key(uplink, caplog):
    def h(req):
        raise httpx.ConnectError(f"connect failed with {KEY}")
    blob, r, logs = run_chat(h, caplog)
    assert_clean(blob, logs)
    assert "transport error" in r["alerts"][0]["error"]


@pytest.mark.parametrize("url", ["https://user:pw@uplink.example.com/v1", "https://pw@uplink.example.com/v1"])
def test_userinfo_rejected_without_echo(url):
    with pytest.raises(ConfigError) as e:
        normalize_uplink_base(url)
    assert "pw" not in str(e.value) and "user:" not in str(e.value)


def test_userinfo_rejected_end_to_end(monkeypatch):
    monkeypatch.setenv("MORPHEUS_MODE", "uplink")
    monkeypatch.setenv("MORPHEUS_BASE_URL", "https://alice:hunter2@uplink.example.com/v1")
    r = server.do_chat([{"role": "user", "content": "hi"}], model="a")
    assert r["status"] == "host_fallback" and "hunter2" not in json.dumps(r)


@pytest.mark.parametrize("url", ["http://localhost:8080/v1", "http://127.0.0.1/v1", "http://[::1]:8000/v1",
                                 "https://uplink.example.com/v1"])
def test_allowed_schemes(url):
    assert normalize_uplink_base(url)[0].endswith("/v1")


@pytest.mark.parametrize("url", ["http://uplink.example.com/v1", "http://10.0.0.5/v1", "ftp://x/v1",
                                 "http://localhost.evil.com/v1", "uplink.example.com/v1"])
def test_rejected_schemes(url):
    with pytest.raises(ConfigError):
        normalize_uplink_base(url)


def test_load_config_rejects_cleartext(monkeypatch):
    monkeypatch.setenv("MORPHEUS_MODE", "uplink")
    monkeypatch.setenv("MORPHEUS_BASE_URL", "http://uplink.example.com/v1")
    with pytest.raises(ConfigError, match="https"):
        load_config()


@pytest.mark.parametrize("given,want", [(None, 60.0), (0, 1.0), (-5, 1.0), (0.2, 1.0), (30, 30.0),
                                        (300, 300.0), (10_000, 300.0), (float("nan"), 60.0), ("x", 60.0)])
def test_timeout_clamped(given, want):
    assert clamp_timeout(given) == want


def test_clamped_timeout_reaches_request(uplink, caplog):
    seen = {}

    def h(req):
        seen["t"] = req.extensions["timeout"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
    c = httpx.Client(transport=httpx.MockTransport(h))
    server.do_chat([{"role": "user", "content": "x"}], timeout_seconds=99999, client=c)
    assert seen["t"]["read"] == 300.0


def test_default_log_level_is_warning():
    server.setup_logging()
    assert logging.getLogger("morpheus_mcp").getEffectiveLevel() == logging.WARNING
    server.setup_logging(verbose=True)
    assert logging.getLogger("morpheus_mcp").getEffectiveLevel() == logging.INFO
    server.setup_logging()


def test_stderr_handler_redacts_key(capsys):
    from morpheus_mcp.redact import register_secret
    register_secret(KEY)
    server.setup_logging()
    logging.getLogger("morpheus_mcp").warning("oops %s", KEY)
    err = capsys.readouterr().err
    assert "oops" in err and KEY not in err
