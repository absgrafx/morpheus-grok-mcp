"""OpenAI-compatible HTTP calls to Morpheus (api.mor.org or an Uplink)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from morpheus_mcp.redact import redact, redact_key_id

logger = logging.getLogger("morpheus_mcp")

DEFAULT_TIMEOUT_SECONDS = 60.0
MIN_TIMEOUT_SECONDS = 1.0
MAX_TIMEOUT_SECONDS = 300.0
MAX_ERROR_MESSAGE = 200
MAX_ERROR_TYPE = 60
_WINDOW = 12  # an upstream message sharing this many consecutive chars with the request is withheld


def clamp_timeout(seconds: float | None) -> float:
    """Clamp an agent-supplied timeout to 1-300 s (default 60 s)."""
    try:
        t = float(seconds) if seconds is not None else DEFAULT_TIMEOUT_SECONDS
    except (TypeError, ValueError):
        t = DEFAULT_TIMEOUT_SECONDS
    if t != t:  # NaN
        t = DEFAULT_TIMEOUT_SECONDS
    return max(MIN_TIMEOUT_SECONDS, min(MAX_TIMEOUT_SECONDS, t))


def request_texts(body: dict[str, Any] | None) -> list[str]:
    """Every string in the request body (prompt text, inputs) so errors can never echo them."""
    out: list[str] = []

    def walk(o: Any) -> None:
        if isinstance(o, str):
            out.append(o)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk({k: v for k, v in (body or {}).items() if k != "model"})
    return out


def _quotes_request(message: str, texts: list[str]) -> bool:
    joined = " ".join(" ".join(texts).split())[:20000]
    if len(joined) < _WINDOW:
        return len(joined) >= 4 and joined in message
    windows = {joined[i:i + _WINDOW] for i in range(len(joined) - _WINDOW + 1)}
    return any(message[i:i + _WINDOW] in windows for i in range(max(0, len(message) - _WINDOW + 1)))


def safe_error_detail(resp: httpx.Response, api_key: str, texts: list[str]) -> str:
    """A short, parsed error message and type from an error response. Never the raw body."""
    try:
        data = resp.json()
    except ValueError:
        return f"non-JSON error body ({len(resp.content)} bytes, not shown)"
    msg, typ = None, None
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            msg, typ = err.get("message"), err.get("type") or err.get("code")
        elif isinstance(err, str):
            msg = err
        if msg is None:
            msg = data.get("detail") if isinstance(data.get("detail"), str) else data.get("message")
    if not isinstance(msg, str) or not msg.strip():
        return "JSON error body without a message (not shown)"
    msg = " ".join(msg.split())
    if _quotes_request(msg, texts):
        msg = "(upstream message withheld: it quoted the request)"
    msg = redact(msg, [api_key])[:MAX_ERROR_MESSAGE]
    out = msg
    if isinstance(typ, (str, int)) and str(typ).strip():
        out = f"{redact(str(typ), [api_key])[:MAX_ERROR_TYPE]}: {msg}"
    return out


class MorpheusHTTPError(Exception):
    """HTTP error, timeout or transport failure. The message is already redacted."""

    def __init__(self, message: str, status_code: int | None = None, kind: str = "http") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.kind = kind  # "http" | "timeout" | "transport" | "bad_response"


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _request(
    method: str,
    base_url: str,
    path: str,
    api_key: str,
    *,
    body: dict[str, Any] | None = None,
    timeout: float | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/{path}"
    logger.info(
        "morpheus_mcp %s %s key=%s%s",
        method, url, redact_key_id(api_key),
        f" model={body.get('model')}" if body and body.get("model") else "",
    )
    secs = clamp_timeout(timeout)
    t = httpx.Timeout(secs, connect=min(10.0, secs))
    texts = request_texts(body)
    own = client is None
    c = client or httpx.Client(timeout=t)
    try:
        resp = c.request(method, url, headers=_headers(api_key), json=body, timeout=t)
    except httpx.TimeoutException as e:
        raise MorpheusHTTPError(
            f"timed out after {secs:g}s ({type(e).__name__})",
            kind="timeout",
        ) from None
    except httpx.HTTPError as e:
        raise MorpheusHTTPError(
            redact(f"transport error: {type(e).__name__}: {e}", [api_key, *texts]), kind="transport"
        ) from None
    finally:
        if own:
            c.close()
    if resp.status_code >= 400:
        raise MorpheusHTTPError(
            f"HTTP {resp.status_code}: {safe_error_detail(resp, api_key, texts)}",
            status_code=resp.status_code,
        )
    try:
        return resp.json()
    except ValueError as e:
        raise MorpheusHTTPError(
            f"HTTP {resp.status_code} but the body is not JSON", status_code=resp.status_code,
            kind="bad_response",
        ) from None


def chat_completions(base_url: str, api_key: str, *, body: dict[str, Any], timeout: float | None = None,
                     client: httpx.Client | None = None) -> dict[str, Any]:
    """POST ``{base}/chat/completions``."""
    return _request("POST", base_url, "chat/completions", api_key, body=body, timeout=timeout, client=client)


def list_models(base_url: str, api_key: str, *, timeout: float | None = None,
                client: httpx.Client | None = None) -> dict[str, Any]:
    """GET ``{base}/models``."""
    return _request("GET", base_url, "models", api_key, timeout=timeout, client=client)


def embeddings(base_url: str, api_key: str, *, body: dict[str, Any], timeout: float | None = None,
               client: httpx.Client | None = None) -> dict[str, Any]:
    """POST ``{base}/embeddings``."""
    return _request("POST", base_url, "embeddings", api_key, body=body, timeout=timeout, client=client)
