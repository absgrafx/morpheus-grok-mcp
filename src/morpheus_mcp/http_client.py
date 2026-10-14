"""OpenAI-compatible HTTP calls to Morpheus (api.mor.org or an Uplink)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from morpheus_mcp.redact import redact, redact_key_id

logger = logging.getLogger("morpheus_mcp")

DEFAULT_TIMEOUT_SECONDS = 60.0


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
    t = httpx.Timeout(timeout or DEFAULT_TIMEOUT_SECONDS, connect=min(10.0, timeout or 10.0))
    own = client is None
    c = client or httpx.Client(timeout=t)
    try:
        resp = c.request(method, url, headers=_headers(api_key), json=body, timeout=t)
    except httpx.TimeoutException as e:
        raise MorpheusHTTPError(
            redact(f"timed out after {timeout or DEFAULT_TIMEOUT_SECONDS:g}s ({type(e).__name__})"),
            kind="timeout",
        ) from e
    except httpx.HTTPError as e:
        raise MorpheusHTTPError(redact(f"transport error: {type(e).__name__}: {e}"), kind="transport") from e
    finally:
        if own:
            c.close()
    if resp.status_code >= 400:
        raise MorpheusHTTPError(
            redact(f"HTTP {resp.status_code}: {resp.text[:300].strip()}"), status_code=resp.status_code
        )
    try:
        return resp.json()
    except ValueError as e:
        raise MorpheusHTTPError(
            f"HTTP {resp.status_code} but the body is not JSON", status_code=resp.status_code,
            kind="bad_response",
        ) from e


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
