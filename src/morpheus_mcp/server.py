"""Morpheus Inference MCP server (stdio) — thin OpenAI-compatible tools."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from morpheus_mcp import __version__
from morpheus_mcp.config import ConfigError, load_config
from morpheus_mcp.http_client import MorpheusHTTPError, chat_completions, embeddings, list_models
from morpheus_mcp.redact import redact

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("morpheus_mcp")

mcp = FastMCP(
    "morpheus-inference",
    instructions=(
        "OpenAI-compatible Morpheus MoE via public api.mor.org or private Uplink. "
        "Use morpheus_chat for analysis by default; list_models for install smoke / picker; "
        "morpheus_embed for embeddings. Never put API keys in prompts."
    ),
)


def _cfg():
    return load_config()


def _assistant_from_chat(data: dict[str, Any]) -> dict[str, Any]:
    """Extract assistant content + tool_calls from a chat/completions response."""
    choices = data.get("choices") or []
    if not choices:
        return {
            "content": None,
            "tool_calls": None,
            "finish_reason": None,
            "raw": data,
        }
    msg = (choices[0] or {}).get("message") or {}
    return {
        "content": msg.get("content"),
        "tool_calls": msg.get("tool_calls"),
        "finish_reason": (choices[0] or {}).get("finish_reason"),
        "model": data.get("model"),
        "id": data.get("id"),
        "usage": data.get("usage"),
    }


@mcp.tool()
def morpheus_chat(
    messages: list[dict[str, Any]],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any | None = None,
) -> str:
    """Call Morpheus OpenAI-compatible chat/completions.

    Pass messages (OpenAI shape). Model defaults to MORPHEUS_MODEL_DEFAULT when omitted.
    Optional tools / tool_choice for models that support tool_calls.
    Returns JSON with assistant content and tool_calls if any.
    """
    try:
        cfg = _cfg()
        use_model = (model or cfg.model_default or "").strip()
        if not use_model:
            raise ConfigError(
                "model is required (pass model= or set MORPHEUS_MODEL_DEFAULT)"
            )
        data = chat_completions(
            cfg.base_url,
            cfg.api_key,
            messages=messages,
            model=use_model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
        )
        out = _assistant_from_chat(data)
        out["endpoint_mode"] = cfg.endpoint_mode
        out["base_url"] = cfg.base_url
        return json.dumps(out, ensure_ascii=False)
    except (ConfigError, MorpheusHTTPError) as e:
        return json.dumps({"error": redact(str(e))}, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001 — surface to host as tool error text
        logger.exception("morpheus_chat failed")
        return json.dumps({"error": redact(str(e))}, ensure_ascii=False)


@mcp.tool()
def morpheus_list_models() -> str:
    """List models from GET {base}/models (install smoke + model picker)."""
    try:
        cfg = _cfg()
        data = list_models(cfg.base_url, cfg.api_key)
        return json.dumps(
            {
                "endpoint_mode": cfg.endpoint_mode,
                "base_url": cfg.base_url,
                "data": data.get("data", data),
            },
            ensure_ascii=False,
        )
    except (ConfigError, MorpheusHTTPError) as e:
        return json.dumps({"error": redact(str(e))}, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        logger.exception("morpheus_list_models failed")
        return json.dumps({"error": redact(str(e))}, ensure_ascii=False)


@mcp.tool()
def morpheus_embed(
    input: str | list[str],
    model: str,
) -> str:
    """Call Morpheus OpenAI-compatible embeddings (POST {base}/embeddings)."""
    try:
        cfg = _cfg()
        data = embeddings(cfg.base_url, cfg.api_key, input=input, model=model)
        return json.dumps(
            {
                "endpoint_mode": cfg.endpoint_mode,
                "base_url": cfg.base_url,
                "model": data.get("model", model),
                "data": data.get("data"),
                "usage": data.get("usage"),
            },
            ensure_ascii=False,
        )
    except (ConfigError, MorpheusHTTPError) as e:
        return json.dumps({"error": redact(str(e))}, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        logger.exception("morpheus_embed failed")
        return json.dumps({"error": redact(str(e))}, ensure_ascii=False)


def main() -> None:
    """stdio entrypoint for uvx / python -m morpheus_mcp."""
    logger.info("morpheus-inference MCP v%s starting (stdio)", __version__)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

