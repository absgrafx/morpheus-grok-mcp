"""Morpheus Inference MCP server (stdio)."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from morpheus_mcp import __version__
from morpheus_mcp.config import ConfigError, load_config
from morpheus_mcp.fallback import Alert, EmptyResponse, handoff, now_iso, run_with_fallback
from morpheus_mcp.http_client import (
    clamp_timeout,
    MorpheusHTTPError,
    chat_completions,
    embeddings,
    list_models,
)
from morpheus_mcp.redact import RedactingFilter, redact

logger = logging.getLogger("morpheus_mcp")


def setup_logging(verbose: bool = False) -> None:
    """stderr logging: WARNING by default (alerts), INFO per request only with --verbose.

    Every record passes through RedactingFilter, so a registered key never reaches stderr.
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)
    root.setLevel(logging.WARNING)
    logger.setLevel(logging.INFO if verbose else logging.WARNING)


setup_logging()

mcp = FastMCP(
    "morpheus-inference",
    instructions=(
        "Optional tools that run chat and embeddings on Morpheus decentralized inference "
        "(api.mor.org or the user's own Uplink). Use them when the user asks for Morpheus or "
        "has enabled it. If a result has status host_fallback, use your own model and show the "
        "user the user_alert text. Never put API keys in prompts or tool arguments."
    ),
)


def server_version() -> str:
    """This package's version (installed metadata, else __version__), not the MCP library's."""
    try:
        from importlib.metadata import PackageNotFoundError, version
        return version("morpheus-mcp")
    except PackageNotFoundError:
        return __version__


# FastMCP has no version argument; without this the MCP library's own version is reported.
mcp._mcp_server.version = server_version()


def _dump(obj: dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _order(first: str | None, rest: tuple[str, ...] | list[str]) -> list[str]:
    out: list[str] = []
    for m in ([first] if first else []) + list(rest):
        m = (m or "").strip()
        if m and m not in out:
            out.append(m)
    return out


def _config_handoff(e: ConfigError) -> dict[str, Any]:
    return handoff([Alert(None, "(not configured)", redact(str(e)), None, now_iso(),
                          "Morpheus is not configured; returned control to the host model.")])


async def _notify(ctx: Context | None, result: dict[str, Any]) -> None:
    """Send alerts to the client as MCP log messages as well as in the result."""
    if ctx is None or not result.get("user_alert"):
        return
    try:
        await ctx.warning(result["user_alert"])
    except Exception:  # noqa: BLE001 — a client without logging support must not break the call
        pass


def chat_body(model: str, messages, temperature, max_tokens, tools, tool_choice) -> dict[str, Any]:
    body: dict[str, Any] = {"model": model, "messages": messages}
    for k, v in (("temperature", temperature), ("max_tokens", max_tokens), ("tools", tools),
                 ("tool_choice", tool_choice)):
        if v is not None:
            body[k] = v
    return body


def extract_chat(data: dict[str, Any]) -> dict[str, Any]:
    choices = data.get("choices") or []
    if not choices:
        raise EmptyResponse("no choices in the response")
    choice = choices[0] or {}
    msg = choice.get("message") or {}
    if not msg.get("content") and not msg.get("tool_calls"):
        raise EmptyResponse("no content and no tool_calls")
    return {
        "content": msg.get("content"),
        "tool_calls": msg.get("tool_calls"),
        "finish_reason": choice.get("finish_reason"),
        "id": data.get("id"),
        "usage": data.get("usage"),
    }


def do_chat(messages, model=None, temperature=None, max_tokens=None, tools=None, tool_choice=None,
            timeout_seconds=None, client=None) -> dict[str, Any]:
    try:
        cfg = load_config()
    except ConfigError as e:
        return _config_handoff(e)
    endpoint = f"{cfg.base_url}/chat/completions"

    def call(m: str) -> dict[str, Any]:
        body = chat_body(m, messages, temperature, max_tokens, tools, tool_choice)
        return extract_chat(chat_completions(cfg.base_url, cfg.api_key, body=body,
                                             timeout=timeout_seconds, client=client))

    return run_with_fallback(endpoint=endpoint, models=_order(model, cfg.models), call=call)


def do_embed(input, model, fallback_models=None, timeout_seconds=None, client=None) -> dict[str, Any]:
    try:
        cfg = load_config()
    except ConfigError as e:
        return _config_handoff(e)
    endpoint = f"{cfg.base_url}/embeddings"

    def call(m: str) -> dict[str, Any]:
        data = embeddings(cfg.base_url, cfg.api_key, body={"model": m, "input": input},
                          timeout=timeout_seconds, client=client)
        if not data.get("data"):
            raise EmptyResponse("no embeddings in the response")
        return {"data": data.get("data"), "usage": data.get("usage")}

    return run_with_fallback(endpoint=endpoint, models=_order(model, fallback_models or []), call=call)


def do_list_models(timeout_seconds=None, client=None) -> dict[str, Any]:
    try:
        cfg = load_config()
    except ConfigError as e:
        return _config_handoff(e)
    try:
        data = list_models(cfg.base_url, cfg.api_key, timeout=timeout_seconds, client=client)
    except MorpheusHTTPError as e:
        a = Alert(None, f"{cfg.base_url}/models", str(e), e.status_code, now_iso(),
                  "Could not list Morpheus models; nothing else was tried.")
        logger.warning("%s", a.text())
        r = handoff([a])
        r["agent_instructions"] = "Show the user the text in user_alert. Morpheus is not reachable right now."
        return r
    ids = [m.get("id") for m in (data.get("data") or []) if isinstance(m, dict)]
    return {"status": "ok", "endpoint": f"{cfg.base_url}/models", "mode": cfg.mode,
            "model_hierarchy": list(cfg.models), "models": ids}


@mcp.tool()
async def morpheus_chat(
    messages: list[dict[str, Any]],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any | None = None,
    timeout_seconds: float | None = None,
    ctx: Context | None = None,
) -> str:
    """Chat completion on Morpheus (OpenAI-compatible messages).

    Tries `model` first (if given), then the configured model hierarchy, one call each.
    Every failure is reported in `alerts` / `user_alert`. If status is "host_fallback",
    no Morpheus model worked: answer with your own model and show the user `user_alert`.
    """
    result = await asyncio.to_thread(do_chat, messages, model, temperature, max_tokens, tools,
                                     tool_choice, clamp_timeout(timeout_seconds))
    await _notify(ctx, result)
    return _dump(result)


@mcp.tool()
async def morpheus_embed(
    input: str | list[str],
    model: str,
    fallback_models: list[str] | None = None,
    timeout_seconds: float | None = None,
    ctx: Context | None = None,
) -> str:
    """Embeddings on Morpheus. Tries `model`, then each of `fallback_models` in order.

    Same alert and host_fallback rules as morpheus_chat.
    """
    result = await asyncio.to_thread(do_embed, input, model, fallback_models,
                                     clamp_timeout(timeout_seconds))
    await _notify(ctx, result)
    return _dump(result)


@mcp.tool()
async def morpheus_list_models(ctx: Context | None = None) -> str:
    """List the model ids available on the configured Morpheus endpoint, and the configured hierarchy."""
    result = await asyncio.to_thread(do_list_models)
    await _notify(ctx, result)
    return _dump(result)


def main() -> None:
    """stdio entry point (uvx morpheus-mcp / python -m morpheus_mcp). Pass --verbose for INFO logs."""
    setup_logging(verbose="--verbose" in sys.argv[1:])
    logger.info("morpheus-inference MCP v%s starting (stdio)", __version__)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
