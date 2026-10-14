"""Configuration for the Morpheus Inference MCP server.

Three settings plus one optional list:

- ``MORPHEUS_API_KEY``  — inference key (required)
- ``MORPHEUS_MODE``     — ``api.mor.org`` (default) or ``uplink``
- ``MORPHEUS_BASE_URL`` — your Uplink base URL (uplink mode only)
- ``MORPHEUS_MODELS``   — optional model hierarchy, comma-separated, most preferred first
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from morpheus_mcp.redact import register_secret

logger = logging.getLogger("morpheus_mcp")

PUBLIC_BASE = "https://api.mor.org/api/v1"
MODE_PUBLIC = "api.mor.org"
MODE_UPLINK = "uplink"
_MODE_ALIASES = {
    "api.mor.org": MODE_PUBLIC,
    "public": MODE_PUBLIC,
    "uplink": MODE_UPLINK,
    "custom": MODE_UPLINK,
}

# Trailing resource paths sometimes pasted into a base URL by mistake
_RESOURCE_SUFFIXES = ("/chat/completions", "/completions", "/embeddings", "/models", "/usage")
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")
_PLACEHOLDER = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$")


class ConfigError(Exception):
    """Configuration problem the user must fix (message never contains a key)."""


def env(name: str) -> str:
    """Read a setting; an unexpanded ``${VAR}`` placeholder counts as unset."""
    val = (os.environ.get(name) or "").strip()
    return "" if _PLACEHOLDER.match(val) else val


def normalize_mode(raw: str | None) -> str:
    mode = (raw or "").strip().lower() or MODE_PUBLIC
    if mode not in _MODE_ALIASES:
        raise ConfigError(f"MORPHEUS_MODE must be 'api.mor.org' or 'uplink', got {raw!r}")
    return _MODE_ALIASES[mode]


def normalize_uplink_base(url: str) -> tuple[str, list[str]]:
    """Normalize an Uplink base URL to end in exactly ``/v1``.

    Strips pasted resource paths, collapses ``/v1/v1``, never adds ``/api``.
    Returns ``(base, warnings)``.
    """
    warnings: list[str] = []
    raw = (url or "").strip()
    if not raw:
        raise ConfigError("MORPHEUS_BASE_URL is required when MORPHEUS_MODE=uplink")
    parsed = urlparse(raw)
    if not parsed.netloc or parsed.scheme.lower() not in ("https", "http"):
        raise ConfigError("MORPHEUS_BASE_URL must be an absolute https:// URL")
    if "@" in parsed.netloc:
        raise ConfigError(
            "MORPHEUS_BASE_URL must not contain a user name or password; put the key in MORPHEUS_API_KEY"
        )
    try:
        host = (parsed.hostname or "").lower()
        parsed.port  # noqa: B018 — raises on a bad port
    except ValueError:
        raise ConfigError("MORPHEUS_BASE_URL has an invalid host or port") from None
    if not host:
        raise ConfigError("MORPHEUS_BASE_URL must include a host")
    if parsed.scheme.lower() == "http" and host not in LOCAL_HOSTS:
        raise ConfigError(
            "MORPHEUS_BASE_URL must use https://; http:// is allowed only for localhost, 127.0.0.1 and ::1"
        )

    path = (parsed.path or "").rstrip("/")
    for suffix in _RESOURCE_SUFFIXES:
        if path.lower().endswith(suffix):
            path = path[: -len(suffix)].rstrip("/")
            warnings.append(f"removed {suffix!r} from the base URL; use the base ending in /v1")
    while re.search(r"/v1/v1$", path, re.IGNORECASE):
        path = path[:-3]
        warnings.append("collapsed a duplicate /v1 in the base URL")
    if not re.search(r"/v1$", path, re.IGNORECASE):
        path = path + "/v1"
        warnings.append("appended /v1 to the base URL")
    if not path.startswith("/"):
        path = "/" + path
    return urlunparse((parsed.scheme.lower(), parsed.netloc, path, "", "", "")), warnings


def parse_models(raw: str | None) -> tuple[str, ...]:
    """Parse the model hierarchy: comma- or newline-separated ids, order kept, duplicates dropped."""
    out: list[str] = []
    for part in re.split(r"[,\n]", raw or ""):
        m = part.strip()
        if m and m not in out:
            out.append(m)
    return tuple(out)


@dataclass(frozen=True)
class RuntimeConfig:
    api_key: str
    mode: str
    base_url: str
    models: tuple[str, ...]
    warnings: tuple[str, ...] = ()


def load_config() -> RuntimeConfig:
    register_secret(env("MORPHEUS_API_KEY"))  # before anything can log or raise
    mode = normalize_mode(env("MORPHEUS_MODE"))
    warnings: list[str] = []
    if mode == MODE_PUBLIC:
        base = PUBLIC_BASE
    else:
        base, warnings = normalize_uplink_base(env("MORPHEUS_BASE_URL"))
        for w in warnings:
            logger.warning("morpheus_mcp: %s", w)
    key = env("MORPHEUS_API_KEY")
    register_secret(key)
    if not key:
        raise ConfigError("MORPHEUS_API_KEY is not set (set it in Plugins > Configure)")
    return RuntimeConfig(
        api_key=key,
        mode=mode,
        base_url=base,
        models=parse_models(env("MORPHEUS_MODELS")),
        warnings=tuple(warnings),
    )
