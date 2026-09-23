"""Endpoint and API-key resolution for Morpheus Inference MCP."""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger("morpheus_mcp")

PUBLIC_BASE = "https://api.mor.org/api/v1"

KNOWN_SLOTS = (
    "cos",
    "cto",
    "ciso",
    "builder",
    "verification",
    "comms",
    "cfo",
)

# Trailing resource paths sometimes pasted into base_url by mistake
_RESOURCE_SUFFIXES = (
    "/chat/completions",
    "/completions",
    "/embeddings",
    "/models",
    "/usage",
)


class ConfigError(Exception):
    """Hard configuration failure (missing per_bot key, master refuse, etc.)."""


def normalize_uplink_base(url: str) -> tuple[str, list[str]]:
    """Normalize a custom Uplink base to exactly ``…/v1``.

    Never invents ``/api`` on Uplink. Never doubles ``/v1``.
    Strips trailing resource paths. Warns (does not hard-fail) on fixes.

    Returns ``(normalized_base, warnings)``.
    """
    warnings: list[str] = []
    raw = (url or "").strip()
    if not raw:
        raise ConfigError("MORPHEUS_BASE_URL is required when MORPHEUS_ENDPOINT_MODE=custom")

    # Drop fragment/query for base construction; keep scheme/host/path
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        # Allow scheme-less host? Require absolute URL.
        raise ConfigError(f"MORPHEUS_BASE_URL must be an absolute URL, got: {raw!r}")

    path = parsed.path or ""
    # Strip trailing slash for suffix checks, then rebuild
    path_stripped = path.rstrip("/")

    for suffix in _RESOURCE_SUFFIXES:
        if path_stripped.lower().endswith(suffix):
            path_stripped = path_stripped[: -len(suffix)]
            warnings.append(
                f"stripped trailing resource path {suffix!r} from custom base; "
                "use the OpenAI-compatible root ending in /v1"
            )
            path_stripped = path_stripped.rstrip("/")

    # Collapse accidental /v1/v1
    while re.search(r"/v1/v1$", path_stripped, re.IGNORECASE):
        path_stripped = re.sub(r"/v1$", "", path_stripped, count=1, flags=re.IGNORECASE)
        warnings.append("collapsed duplicate /v1 in custom base")

    # Ensure exactly one trailing /v1 — never invent /api on Uplink
    if not re.search(r"/v1$", path_stripped, re.IGNORECASE):
        # If path ends with /api only, do NOT turn into /api/v1 (that is APIGW shape).
        # Append /v1 to whatever we have (including empty → /v1).
        if path_stripped.lower().endswith("/api"):
            warnings.append(
                "custom base ends with /api; Uplink expects /v1 (no /api). "
                "appending /v1 → …/api/v1 — verify this is intentional"
            )
        path_stripped = path_stripped + "/v1"
        warnings.append("appended /v1 to custom base (auto-normalize)")

    # Reject accidental public APIGW path shape when user meant Uplink? Soft warn only.
    if "/api/v1" in path_stripped.lower() and "api.mor.org" not in parsed.netloc.lower():
        warnings.append(
            "custom base contains /api/v1; private Uplink normally uses /v1 without /api"
        )

    new_path = path_stripped if path_stripped.startswith("/") else "/" + path_stripped
    normalized = urlunparse((parsed.scheme, parsed.netloc, new_path, "", "", ""))
    # Canonical: no trailing slash after /v1
    normalized = normalized.rstrip("/")
    return normalized, warnings


def resolve_base_url(
    endpoint_mode: str | None = None,
    base_url: str | None = None,
) -> tuple[str, list[str]]:
    """Resolve OpenAI-compatible base from endpoint mode."""
    mode = (endpoint_mode or os.environ.get("MORPHEUS_ENDPOINT_MODE") or "public").strip().lower()
    warnings: list[str] = []

    if mode == "public":
        return PUBLIC_BASE, warnings
    if mode != "custom":
        raise ConfigError(
            f"MORPHEUS_ENDPOINT_MODE must be 'public' or 'custom', got {mode!r}"
        )

    raw = base_url if base_url is not None else os.environ.get("MORPHEUS_BASE_URL", "")
    normalized, w = normalize_uplink_base(raw)
    warnings.extend(w)
    for msg in warnings:
        logger.warning("morpheus_mcp: %s", msg)
    return normalized, warnings


def _slot_from_env() -> str | None:
    for var in ("MORPHEUS_AGENT_SLOT", "MORPHEUS_AGENT"):
        val = (os.environ.get(var) or "").strip().lower()
        if val:
            return val
    return None


def _refuse_master(slot: str | None) -> None:
    role = (os.environ.get("MORPHEUS_UPLINK_KEY_ROLE") or "").strip().lower()
    key_role = (os.environ.get("MORPHEUS_KEY_ROLE") or "").strip().lower()
    if slot == "master":
        raise ConfigError(
            "refusing master key for inference — master/usage-only keys are not allowed "
            "for chat, embeddings, or list_models"
        )
    if role == "master_usage_only" or key_role in ("master", "master_usage_only"):
        raise ConfigError(
            "refusing master/usage-only key for inference "
            "(MORPHEUS_UPLINK_KEY_ROLE / MORPHEUS_KEY_ROLE)"
        )


def _discrete_slot_key(slot: str) -> str | None:
    env_name = f"MORPHEUS_API_KEY_{slot.upper()}"
    val = os.environ.get(env_name)
    if val is not None and val.strip():
        return val.strip()
    return None


def _json_map_key(slot: str) -> str | None:
    raw = os.environ.get("MORPHEUS_API_KEYS_JSON") or ""
    raw = raw.strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ConfigError(f"MORPHEUS_API_KEYS_JSON is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError("MORPHEUS_API_KEYS_JSON must be a JSON object mapping slot → key")
    # Prefer exact lowercase slot; also accept original keys case-insensitively
    if slot in data and data[slot]:
        return str(data[slot]).strip()
    for k, v in data.items():
        if str(k).lower() == slot and v:
            return str(v).strip()
    return None


def resolve_api_key(
    key_mode: str | None = None,
    agent_slot: str | None = None,
) -> tuple[str, str]:
    """Resolve Bearer API key.

    Returns ``(key, resolution_label)`` where label is for logs (no secret).

    per_bot: discrete ``MORPHEUS_API_KEY_<SLOT>`` then JSON map. Hard-fail if missing.
    Never silently falls back to shared when per_bot.
    """
    mode = (key_mode or os.environ.get("MORPHEUS_KEY_MODE") or "shared").strip().lower()
    slot = (agent_slot or _slot_from_env() or "").strip().lower() or None

    _refuse_master(slot)

    if mode == "shared":
        key = (os.environ.get("MORPHEUS_API_KEY") or "").strip()
        if not key:
            raise ConfigError("MORPHEUS_API_KEY is required when MORPHEUS_KEY_MODE=shared")
        return key, "shared"

    if mode != "per_bot":
        raise ConfigError(
            f"MORPHEUS_KEY_MODE must be 'shared' or 'per_bot', got {mode!r}"
        )

    if not slot:
        raise ConfigError(
            "MORPHEUS_KEY_MODE=per_bot requires MORPHEUS_AGENT_SLOT or MORPHEUS_AGENT"
        )

    discrete = _discrete_slot_key(slot)
    if discrete:
        return discrete, f"per_bot:discrete:{slot}"

    mapped = _json_map_key(slot)
    if mapped:
        return mapped, f"per_bot:json_map:{slot}"

    raise ConfigError(
        f"per_bot key missing for slot {slot!r}: set MORPHEUS_API_KEY_{slot.upper()} "
        f"or include {slot!r} in MORPHEUS_API_KEYS_JSON (no silent shared fallback)"
    )


@dataclass(frozen=True)
class RuntimeConfig:
    base_url: str
    api_key: str
    key_label: str
    endpoint_mode: str
    key_mode: str
    model_default: str | None
    warnings: tuple[str, ...]


def load_config() -> RuntimeConfig:
    """Load full runtime config from environment."""
    endpoint_mode = (os.environ.get("MORPHEUS_ENDPOINT_MODE") or "public").strip().lower()
    key_mode = (os.environ.get("MORPHEUS_KEY_MODE") or "shared").strip().lower()
    base, warnings = resolve_base_url(endpoint_mode)
    key, key_label = resolve_api_key(key_mode)
    model_default = (os.environ.get("MORPHEUS_MODEL_DEFAULT") or "").strip() or None
    return RuntimeConfig(
        base_url=base,
        api_key=key,
        key_label=key_label,
        endpoint_mode=endpoint_mode,
        key_mode=key_mode,
        model_default=model_default,
        warnings=tuple(warnings),
    )

