import pytest

from morpheus_mcp.config import (PUBLIC_BASE, ConfigError, load_config, normalize_mode,
                                 normalize_uplink_base, parse_models)


def test_default_mode_is_public():
    cfg = load_config()
    assert cfg.mode == "api.mor.org"
    assert cfg.base_url == PUBLIC_BASE


def test_public_mode_ignores_base_url(monkeypatch):
    monkeypatch.setenv("MORPHEUS_MODE", "api.mor.org")
    monkeypatch.setenv("MORPHEUS_BASE_URL", "https://other.example/v1")
    assert load_config().base_url == PUBLIC_BASE


def test_uplink_mode_uses_base_url(monkeypatch):
    monkeypatch.setenv("MORPHEUS_MODE", "uplink")
    monkeypatch.setenv("MORPHEUS_BASE_URL", "https://uplink.example.com")
    assert load_config().base_url == "https://uplink.example.com/v1"


def test_uplink_mode_requires_base_url(monkeypatch):
    monkeypatch.setenv("MORPHEUS_MODE", "uplink")
    with pytest.raises(ConfigError, match="MORPHEUS_BASE_URL"):
        load_config()


def test_missing_key(monkeypatch):
    monkeypatch.delenv("MORPHEUS_API_KEY")
    with pytest.raises(ConfigError, match="MORPHEUS_API_KEY"):
        load_config()


def test_unexpanded_placeholders_count_as_unset(monkeypatch):
    monkeypatch.setenv("MORPHEUS_MODE", "${MORPHEUS_MODE}")
    monkeypatch.setenv("MORPHEUS_MODELS", "${MORPHEUS_MODELS}")
    cfg = load_config()
    assert cfg.mode == "api.mor.org" and cfg.models == ()


@pytest.mark.parametrize("raw,mode", [("api.mor.org", "api.mor.org"), ("public", "api.mor.org"),
                                       ("UPLINK", "uplink"), ("custom", "uplink"), ("", "api.mor.org")])
def test_modes(raw, mode):
    assert normalize_mode(raw) == mode


def test_bad_mode():
    with pytest.raises(ConfigError):
        normalize_mode("openai")


@pytest.mark.parametrize("raw,want", [
    ("https://u.example/v1", "https://u.example/v1"),
    ("https://u.example/v1/", "https://u.example/v1"),
    ("https://u.example/v1/chat/completions", "https://u.example/v1"),
    ("https://u.example/v1/v1", "https://u.example/v1"),
    ("https://u.example/", "https://u.example/v1"),
])
def test_normalize_uplink(raw, want):
    assert normalize_uplink_base(raw)[0] == want


def test_normalize_rejects_relative():
    with pytest.raises(ConfigError):
        normalize_uplink_base("u.example/v1")


def test_parse_models_keeps_order_and_dedupes():
    assert parse_models(" a, b ,a,\nc,, ") == ("a", "b", "c")


def test_errors_never_contain_key(monkeypatch):
    monkeypatch.setenv("MORPHEUS_MODE", "bogus")
    with pytest.raises(ConfigError) as e:
        load_config()
    assert "sk-test" not in str(e.value)


def test_bracketed_host_with_userinfo_is_config_error():
    import pytest as _pytest

    from morpheus_mcp.config import ConfigError, normalize_uplink_base

    with _pytest.raises(ConfigError) as e:
        normalize_uplink_base("http://[::1]@evil")
    assert "evil" not in str(e.value)
