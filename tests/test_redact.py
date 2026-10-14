"""Redaction tests — logs must never leak raw sk-… material."""

from morpheus_mcp.redact import redact, redact_key_id


def test_redact_sk() -> None:
    raw = "Authorization Bearer sk-abcDEF1234567890 failed"
    out = redact(raw)
    assert "sk-abcDEF1234567890" not in out
    assert "[redacted]" in out


def test_redact_key_id_short() -> None:
    assert redact_key_id("sk-abcdefghijklmnop") == "…mnop"
    assert redact_key_id(None) == "(none)"
    assert redact_key_id("") == "(none)"



def test_registered_secret_any_format_is_redacted():
    from morpheus_mcp.redact import register_secret
    register_secret("ukey_SECRETVALUE123")
    out = redact("token=ukey_SECRETVALUE123 and Bearer abc.def https://u:p@h/v1")
    assert "ukey_SECRETVALUE123" not in out and "abc.def" not in out and "u:p@" not in out
