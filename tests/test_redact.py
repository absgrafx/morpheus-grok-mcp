"""Redaction tests — logs must never leak raw sk-… material."""

from morpheus_mcp.redact import redact, redact_key_id


def test_redact_sk() -> None:
    raw = "Authorization Bearer sk-abcDEF1234567890 failed"
    out = redact(raw)
    assert "sk-abcDEF1234567890" not in out
    assert "sk-…" in out


def test_redact_key_id_short() -> None:
    assert redact_key_id("sk-abcdefghijklmnop") == "sk-…mnop"
    assert redact_key_id(None) == "(none)"
    assert redact_key_id("") == "(none)"

