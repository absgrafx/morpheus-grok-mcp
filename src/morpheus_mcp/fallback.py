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

from morpheus_mcp.http_client import MorpheusHTTPError
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
    "Morpheus answered with a different model than the one requested. Show the user the text "
    "in user_alert along with the answer."
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

    def text(self) -> str:
        return (
            f"Morpheus alert at {self.time}: requested model {self.requested} on {self.endpoint} "
            f"was served by {self.served}. The answer is from {self.served}."
        )


_SEP_RE = re.compile(r"[\s_\-]+")


def _norm(name: str) -> str:
    return _SEP_RE.sub("-", name.strip().lower()).strip("-")


def same_model(requested: str, served: str) -> bool:
    """True for an exact, case-insensitive or obvious alias match.

    Aliases: whitespace, '-' / ' ' / '_' treated alike, and a provider prefix
    ('org/name') on either side when the part after the last '/' matches, or a
    dash-separated prefix on either side when the shorter name has at least three
    parts (an Uplink serves BGE-EN-ICL as text-embedding-bge-en-icl).
    """
    a, b = _norm(requested), _norm(served)
    a, b = a.rsplit("/", 1)[-1], b.rsplit("/", 1)[-1]
    if a == b:
        return True
    short, long_ = sorted((a, b), key=len)
    return short.count("-") >= 2 and long_.endswith("-" + short)


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
) -> dict[str, Any]:
    """Try ``call(model)`` for each model in order. Returns a JSON-able dict."""
    alerts: list[Alert | SubstitutionAlert] = []

    def alert(a: Alert | SubstitutionAlert) -> None:
        alerts.append(a)
        logger.warning("%s", a.text())
        if on_alert:
            on_alert(a)

    if not models:
        alert(Alert(None, endpoint, "no model given and MORPHEUS_MODELS is empty", None, clock(),
                    "No Morpheus model to try; returned control to the host model."))
        return handoff(alerts)

    for i, model in enumerate(models):
        try:
            data = call(model)
        except Exception as exc:  # noqa: BLE001 — every failure becomes an alert
            err, code = _fail_details(exc)
            nxt = models[i + 1] if i + 1 < len(models) else None
            if code in AUTH_CODES:
                action = ("The API key was rejected, so other Morpheus models were not tried; "
                          "returned control to the host model.")
                alert(Alert(model, endpoint, err, code, clock(), action))
                return handoff(alerts)
            if nxt:
                action = f"Tried the next Morpheus model, {nxt}."
            else:
                action = "No Morpheus model left; returned control to the host model."
            alert(Alert(model, endpoint, err, code, clock(), action))
            continue
        data = dict(data)
        served = data.pop("served_model", None)
        served = redact(served.strip())[:200] if isinstance(served, str) and served.strip() else None
        out: dict[str, Any] = {"status": "ok", "model_used": served or model,
                               "requested_model": model, "endpoint": endpoint, **data}
        if served and not same_model(model, served):
            alert(SubstitutionAlert(redact(model), served, endpoint, clock()))
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
