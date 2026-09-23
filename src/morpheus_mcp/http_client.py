"""OpenAI-compatible HTTP calls to Morpheus (public APIGW or private Uplink)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from morpheus_mcp.redact import redact, redact_key_id

logger = logging.getLogger("morpheus_mcp")

DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


class MorpheusHTTPError(Exception):
    """Upstream HTTP or transport failure (message already redacted)."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _log_request(method: str, url: str, key: str, model: str | None = None) -> None:
    extra = f" model={model}" if model else ""
    logger.info(
        "morpheus_mcp %s %s key=%s%s",
        method,
        url,
        redact_key_id(key),
        extra,
    )


def chat_completions(
    base_url: str,
    api_key: str,
    *,
    messages: list[dict[str, Any]],
    model: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any | None = None,
    timeout: httpx.Timeout | None = None,
) -> dict[str, Any]:
    """POST ``{base}/chat/completions``. Returns the JSON body."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    body: dict[str, Any] = {"model": model, "messages": messages}
    if temperature is not None:
        body["temperature"] = temperature
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    if tools is not None:
        body["tools"] = tools
    if tool_choice is not None:
        body["tool_choice"] = tool_choice

    _log_request("POST", url, api_key, model)
    try:
        with httpx.Client(timeout=timeout or DEFAULT_TIMEOUT) as client:
            resp = client.post(url, headers=_headers(api_key), json=body)
    except httpx.HTTPError as e:
        raise MorpheusHTTPError(redact(f"transport error: {e}")) from e

    if resp.status_code >= 400:
        raise MorpheusHTTPError(
            redact(f"chat/completions HTTP {resp.status_code}: {resp.text[:500]}"),
            status_code=resp.status_code,
        )
    return resp.json()


def list_models(
    base_url: str,
    api_key: str,
    *,
    timeout: httpx.Timeout | None = None,
) -> dict[str, Any]:
    """GET ``{base}/models``."""
    url = f"{base_url.rstrip('/')}/models"
    _log_request("GET", url, api_key)
    try:
        with httpx.Client(timeout=timeout or DEFAULT_TIMEOUT) as client:
            resp = client.get(url, headers=_headers(api_key))
    except httpx.HTTPError as e:
        raise MorpheusHTTPError(redact(f"transport error: {e}")) from e

    if resp.status_code >= 400:
        raise MorpheusHTTPError(
            redact(f"models HTTP {resp.status_code}: {resp.text[:500]}"),
            status_code=resp.status_code,
        )
    return resp.json()


def embeddings(
    base_url: str,
    api_key: str,
    *,
    input: str | list[str],
    model: str,
    timeout: httpx.Timeout | None = None,
) -> dict[str, Any]:
    """POST ``{base}/embeddings``."""
    url = f"{base_url.rstrip('/')}/embeddings"
    body = {"model": model, "input": input}
    _log_request("POST", url, api_key, model)
    try:
        with httpx.Client(timeout=timeout or DEFAULT_TIMEOUT) as client:
            resp = client.post(url, headers=_headers(api_key), json=body)
    except httpx.HTTPError as e:
        raise MorpheusHTTPError(redact(f"transport error: {e}")) from e

    if resp.status_code >= 400:
        raise MorpheusHTTPError(
            redact(f"embeddings HTTP {resp.status_code}: {resp.text[:500]}"),
            status_code=resp.status_code,
        )
    return resp.json()

