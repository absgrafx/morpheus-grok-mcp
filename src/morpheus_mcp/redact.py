"""Redact secrets from logs and error strings."""

from __future__ import annotations

import re

# OpenAI-style and similar bearer keys: sk-… (keep prefix + ellipsis form in docs)
_SK_RE = re.compile(r"sk-[A-Za-z0-9_\-]{4,}")


def redact(text: str) -> str:
    """Replace raw sk-… material with sk-… for safe logging / errors."""
    if not text:
        return text
    return _SK_RE.sub("sk-…", text)


def redact_key_id(key: str | None) -> str:
    """Short redacted id for logs (never full secret)."""
    if not key:
        return "(none)"
    if key.startswith("sk-") and len(key) > 8:
        return f"sk-…{key[-4:]}"
    if len(key) > 8:
        return f"…{key[-4:]}"
    return "sk-…"

