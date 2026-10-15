"""Model hierarchy, fallback and alerts.

Rules:
- Models are tried in order: the model the agent asked for (if any), then the
  configured hierarchy (MORPHEUS_MODELS).
- Each model is called once. On an error or timeout the next model is tried.
  Nothing is retried silently: every failure produces an alert.
- 401/403 means the key itself was rejected; other models use the same key, so
  control goes straight back to the host model.
- When no Morpheus model is left, the result tells the agent to answer with its
  own (host) model and to show the alert to the user.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from dataclasses import asdict, dataclass
from typing import Any, Callable

from morpheus_mcp.http_client import MorpheusHTTPError, _quotes_request
from morpheus_mcp.redact import redact

logger = logging.getLogger("morpheus_mcp")

HOST_FALLBACK_INSTRUCTIONS = (
    "Morpheus could not complete this request. Use your own model to handle it now. "
    "First show the user the text in user_alert, then continue with your own model."
)
SHOW_ALERT_INSTRUCTIONS = (
    "Morpheus answered, but only after a fallback. Show the user the text in user_alert "
    "along with the answer."
)
SUBSTITUTION_INSTRUCTIONS = (
    "Morpheus answered. The endpoint chose a different model than the one requested; this is "
    "informational, not a failure. Mention the user_alert text to the user along with the answer."
)
AUTH_CODES = (401, 403)


def now_iso() -> str:
    """Local time with its UTC offset, to the second."""
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass
class Alert:
    model: str | None
    endpoint: str
    error: str
    http_status: int | None
    time: str
    action: str

    def text(self) -> str:
        code = f"HTTP {self.http_status}" if self.http_status else "no HTTP response"
        return (
            f"Morpheus alert at {self.time}: model {self.model or '(none)'} on {self.endpoint} "
            f"failed ({code}; {self.error}). Action: {self.action}"
        )


@dataclass
class SubstitutionAlert:
    """The endpoint answered with a different model than the one requested."""
    requested: str
    served: str
    endpoint: str
    time: str
    type: str = "model_substituted"
    severity: str = "info"

    def text(self) -> str:
        return (
            f'Morpheus note at {self.time}: served by "{self.served}" instead of "{self.requested}" '
            f"on {self.endpoint} (the endpoint picked the model)."
        )


INVALID_MODEL_NAME = "(invalid model name)"
MAX_MODEL_NAME = 100
MAX_SUBSTITUTED_NAME = 64
MAX_NAME_TOKENS = 8
_TOKEN_SPLIT_RE = re.compile(r"[._:/@+\-]+")
# Sub-words inside a token: camelCase humps, ALLCAPS runs and digit runs.
_SUBWORD_RE = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|[0-9]+")
# Whole tokens (case-insensitive) that a real model id never needs. "instruct" is not here.
DENY_TOKENS = frozenset({
    "system", "ignore", "previous", "instruction", "instructions", "assistant", "user",
    "prompt", "paste", "api", "apikey", "key", "secret", "password", "token", "override",
})
_MODEL_NAME_RE = re.compile(r"[A-Za-z0-9._:/@+\- ]+")
_SEP_RE = re.compile(r"[\s_\-]+")

# Known aliases, keyed by the normalised requested name. Values are normalised served names.
MODEL_ALIASES: dict[str, set[str]] = {
    "bge-en-icl": {"text-embedding-bge-en-icl"},
}


def clean_model_name(name: Any, request_texts: list[str] | tuple[str, ...] = ()) -> str | None:
    """A model name that is safe to echo, or INVALID_MODEL_NAME.

    Model names from upstream (and from the agent) are untrusted: they reach the
    agent in user_alert, MCP log messages and stderr. Only [A-Za-z0-9._:/@+-] and
    single inner spaces (catalog names such as "Aion 3.5 Mini") are allowed, up to
    100 characters. Anything else, a truncation, a registered secret or an echo of
    the request text gives INVALID_MODEL_NAME. None or empty stays None.
    """
    if name is None:
        return None
    if not isinstance(name, str):
        return INVALID_MODEL_NAME
    v = name.strip()
    if not v:
        return None
    if (len(v) > MAX_MODEL_NAME or not _MODEL_NAME_RE.fullmatch(v) or "  " in v
            or redact(v) != v or (request_texts and _quotes_request(v, list(request_texts)))):
        return INVALID_MODEL_NAME
    return v


def suspicious_model_name(name: str) -> bool:
    """Stricter check for a served name that is not the requested model or an alias."""
    if len(name) > MAX_SUBSTITUTED_NAME:
        return True
    tokens = [t for t in _TOKEN_SPLIT_RE.split(name) if t]
    if len(tokens) > MAX_NAME_TOKENS:  # separator tokens only
        return True
    words = {t.lower() for t in tokens}
    for t in tokens:
        words.update(w.lower() for w in _SUBWORD_RE.findall(t))
    return any(w in DENY_TOKENS for w in words)


def _norm(name: str) -> str:
    return _SEP_RE.sub("-", name.strip().lower()).strip("-")


def same_model(requested: str, served: str) -> bool:
    """True when the served name is the requested model.

    A match is: equal after lowercasing and treating ' ', '_' and '-' alike (so
    both have the same org, or neither has one); a vendor self-prefix on a request
    with no org ('deepseek/deepseek-v4-flash' for 'DeepSeek V4 Flash'); or a pair in
    MODEL_ALIASES.
    Anything else is a substitution.
    """
    if not isinstance(requested, str) or not isinstance(served, str):
        return False
    if INVALID_MODEL_NAME in (requested, served):
        return False
    a, b = _norm(requested), _norm(served)
    if a == b:
        return True
    a_org, _, a_name = a.rpartition("/")
    b_org, _, b_name = b.rpartition("/")
    if a_name == b_name and a_org == b_org:
        return True
    # Vendor self-prefix: a request with no org may be served as "<org>/<name>" only when
    # the name itself starts with that org (deepseek/deepseek-v4-flash). Any other added
    # org (evilorg/llama-3-70b, meta/llama-3-70b) is a different publisher and is noted.
    if not a_org and b_org and a_name == b_name and b_name.startswith(b_org):
        return True
    return b in MODEL_ALIASES.get(a, set())


class EmptyResponse(Exception):
    """A 2xx response with nothing usable in it."""


def _fail_details(exc: Exception) -> tuple[str, int | None]:
    if isinstance(exc, MorpheusHTTPError):
        msg = str(exc)
        prefix = f"HTTP {exc.status_code}: "
        if exc.status_code and msg.startswith(prefix):
            msg = msg[len(prefix):]  # the alert already shows the status code
        return msg, exc.status_code
    if isinstance(exc, EmptyResponse):
        return f"empty response: {exc}", None
    # The message of an unexpected exception may quote the request, so it is never shown.
    return f"unexpected error ({type(exc).__name__}; message not shown)", None


def run_with_fallback(
    *,
    endpoint: str,
    models: list[str],
    call: Callable[[str], dict[str, Any]],
    on_alert: Callable[[Alert], None] | None = None,
    clock: Callable[[], str] = now_iso,
    request_texts: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    """Try ``call(model)`` for each model in order. Returns a JSON-able dict."""
    alerts: list[Alert | SubstitutionAlert] = []

    def alert(a: Alert | SubstitutionAlert) -> None:
        alerts.append(a)
        if isinstance(a, SubstitutionAlert):
            logger.info("%s", a.text())  # informational: shown on stderr with --verbose
        else:
            logger.warning("%s", a.text())
        if on_alert:
            on_alert(a)

    if not models:
        alert(Alert(None, endpoint, "no model given and MORPHEUS_MODELS is empty", None, clock(),
                    "No Morpheus model to try; returned control to the host model."))
        return handoff(alerts)

    for i, model in enumerate(models):
        # Model ids come from the request or MORPHEUS_MODELS. They are checked for allowed characters,
        # length and the key, but not the prompt-echo check: a prompt may name them.
        shown = clean_model_name(model) or model
        try:
            data = call(model)
        except Exception as exc:  # noqa: BLE001 — every failure becomes an alert
            err, code = _fail_details(exc)
            nxt = models[i + 1] if i + 1 < len(models) else None
            nxt = clean_model_name(nxt) if nxt else None
            if code in AUTH_CODES:
                action = ("The API key was rejected, so other Morpheus models were not tried; "
                          "returned control to the host model.")
                alert(Alert(shown, endpoint, err, code, clock(), action))
                return handoff(alerts)
            if nxt:
                action = f"Tried the next Morpheus model, {nxt}."
            else:
                action = "No Morpheus model left; returned control to the host model."
            alert(Alert(shown, endpoint, err, code, clock(), action))
            continue
        data = dict(data)
        requested = shown
        raw = data.pop("served_model", None)
        raw = raw.strip() if isinstance(raw, str) else None
        # Substitution is decided on the raw names; the raw served name is never displayed.
        substituted = bool(raw) and not same_model(model, raw)
        if not raw:
            served = None
        elif not substituted:
            # The served name is the requested model: skip only the prompt-echo check.
            served = clean_model_name(raw)
        else:
            served = clean_model_name(raw, request_texts)
            if served and (" " in served or suspicious_model_name(served)):
                # A served name may contain spaces only when it names the requested model
                # (or an alias); otherwise a sentence could reach the agent as a model name.
                served = INVALID_MODEL_NAME
        out: dict[str, Any] = {"status": "ok", "model_used": served or requested,
                               "requested_model": requested, "endpoint": endpoint, **data}
        if substituted:
            alert(SubstitutionAlert(requested, served or INVALID_MODEL_NAME, endpoint, clock()))
        if alerts:
            out["alerts"] = [asdict(a) for a in alerts]
            out["user_alert"] = "\n".join(a.text() for a in alerts)
            only_sub = all(isinstance(a, SubstitutionAlert) for a in alerts)
            out["agent_instructions"] = SUBSTITUTION_INSTRUCTIONS if only_sub else SHOW_ALERT_INSTRUCTIONS
        return out
    return handoff(alerts)


def handoff(alerts: list[Alert]) -> dict[str, Any]:
    return {
        "status": "host_fallback",
        "use_host_model": True,
        "agent_instructions": HOST_FALLBACK_INSTRUCTIONS,
        "user_alert": "\n".join(a.text() for a in alerts),
        "alerts": [asdict(a) for a in alerts],
    }
