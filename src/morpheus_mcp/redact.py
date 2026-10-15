"""Redact secrets from logs, alerts and error strings.

The configured API key is registered at load time and replaced literally,
whatever its format. sk-... strings and Bearer tokens are masked as well.
"""

from __future__ import annotations

import logging
import re

_SK_RE = re.compile(r"sk-[A-Za-z0-9_\-]{4,}")
_BEARER_RE = re.compile(r"(?i)(bearer\s+)[^\s\"',;]+")
_USERINFO_RE = re.compile(r"(?i)(https?://)[^/\s@]+@")
_SECRETS: set[str] = set()
MASK = "[redacted]"


def register_secret(value: str | None) -> None:
    """Remember a secret so every later redact() call removes it."""
    v = (value or "").strip()
    if len(v) >= 4:
        _SECRETS.add(v)


def redact(text: str, extra: list[str] | tuple[str, ...] = ()) -> str:
    """Remove registered secrets, ``extra`` strings, sk-... keys, Bearer tokens and URL credentials."""
    if not text:
        return text
    for s in sorted({*_SECRETS, *[e for e in extra if e and len(e) >= 4]}, key=len, reverse=True):
        text = text.replace(s, MASK)
    text = _SK_RE.sub("sk-…", text)
    text = _BEARER_RE.sub(r"\1" + MASK, text)
    return _USERINFO_RE.sub(r"\1" + MASK + "@", text)


_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def strip_control(text: str) -> str:
    """Replace newlines, ANSI escapes and other control characters with a space."""
    return _CONTROL_RE.sub(" ", text) if text else text


def redact_key_id(key: str | None) -> str:
    """Short id for logs: the last 4 characters only."""
    if not key:
        return "(none)"
    if len(key) > 8:
        return f"…{key[-4:]}"
    return "…"


class RedactingFilter(logging.Filter):
    """Applied to the stderr handler so nothing logged can carry a registered secret."""

    def filter(self, record: logging.LogRecord) -> bool:
        # One record is one line: control characters (newlines, ANSI escapes) from any
        # interpolated value are replaced, so nothing can forge or recolour log lines.
        record.msg = strip_control(redact(record.getMessage()))
        record.args = ()
        return True
