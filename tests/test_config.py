"""Unit tests for base URL normalization and key resolution."""

from __future__ import annotations

import json
import os

import pytest

from morpheus_mcp.config import (
    PUBLIC_BASE,
    ConfigError,
    normalize_uplink_base,
    resolve_api_key,
    resolve_base_url,
)


def test_public_base_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MORPHEUS_ENDPOINT_MODE", "public")
    monkeypatch.setenv("MORPHEUS_BASE_URL", "https://evil.example/v1")
    base, warnings = resolve_base_url()
    assert base == PUBLIC_BASE
    assert base == "https://api.mor.org/api/v1"
    assert warnings == []


def test_normalize_appends_v1() -> None:
    base, warnings = normalize_uplink_base("https://uplink.example.com")
    assert base == "https://uplink.example.com/v1"
    assert any("appended /v1" in w for w in warnings)


def test_normalize_keeps_single_v1() -> None:
    base, warnings = normalize_uplink_base("https://uplink.example.com/v1")
    assert base == "https://uplink.example.com/v1"
    assert not any("appended" in w for w in warnings)


def test_normalize_strips_chat_completions() -> None:
    base, warnings = normalize_uplink_base(
        "https://uplink.example.com/v1/chat/completions"
    )
    assert base == "https://uplink.example.com/v1"
    assert any("stripped" in w for w in warnings)


def test_normalize_strips_models_and_embeddings() -> None:
    b1, _ = normalize_uplink_base("https://uplink.example.com/v1/models")
    b2, _ = normalize_uplink_base("https://uplink.example.com/v1/embeddings")
    assert b1 == "https://uplink.example.com/v1"
    assert b2 == "https://uplink.example.com/v1"


def test_normalize_collapses_double_v1() -> None:
    base, warnings = normalize_uplink_base("https://uplink.example.com/v1/v1")
    assert base == "https://uplink.example.com/v1"
    assert any("duplicate" in w for w in warnings)


def test_normalize_never_invents_api_on_bare_host() -> None:
    base, _ = normalize_uplink_base("https://uplink.example.com")
    assert "/api/" not in base
    assert base.endswith("/v1")


def test_normalize_warns_on_api_v1_custom() -> None:
    base, warnings = normalize_uplink_base("https://uplink.example.com/api/v1")
    assert base == "https://uplink.example.com/api/v1"
    assert any("/api/v1" in w for w in warnings)


def test_custom_empty_hard_fail() -> None:
    with pytest.raises(ConfigError, match="required"):
        normalize_uplink_base("")


def test_shared_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MORPHEUS_KEY_MODE", "shared")
    monkeypatch.setenv("MORPHEUS_API_KEY", "sk-shared-test-key")
    monkeypatch.delenv("MORPHEUS_AGENT_SLOT", raising=False)
    monkeypatch.delenv("MORPHEUS_AGENT", raising=False)
    key, label = resolve_api_key()
    assert key == "sk-shared-test-key"
    assert label == "shared"


def test_per_bot_discrete_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MORPHEUS_KEY_MODE", "per_bot")
    monkeypatch.setenv("MORPHEUS_AGENT_SLOT", "cio")
    monkeypatch.setenv("MORPHEUS_API_KEY_CIO", "sk-cio-discrete")
    monkeypatch.setenv("MORPHEUS_API_KEY", "sk-shared-should-not-use")
    key, label = resolve_api_key()
    assert key == "sk-cio-discrete"
    assert label == "per_bot:discrete:cio"


def test_per_bot_json_map_escape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MORPHEUS_KEY_MODE", "per_bot")
    monkeypatch.setenv("MORPHEUS_AGENT", "cto")
    monkeypatch.delenv("MORPHEUS_API_KEY_CTO", raising=False)
    monkeypatch.setenv(
        "MORPHEUS_API_KEYS_JSON",
        json.dumps({"cto": "sk-cto-from-map", "cos": "sk-cos-map"}),
    )
    key, label = resolve_api_key()
    assert key == "sk-cto-from-map"
    assert label == "per_bot:json_map:cto"


def test_per_bot_json_map_arbitrary_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON-map escape accepts arbitrary slot keys (not only known roles)."""
    monkeypatch.setenv("MORPHEUS_KEY_MODE", "per_bot")
    monkeypatch.setenv("MORPHEUS_AGENT_SLOT", "legacy_alias")
    monkeypatch.delenv("MORPHEUS_API_KEY_LEGACY_ALIAS", raising=False)
    monkeypatch.setenv(
        "MORPHEUS_API_KEYS_JSON",
        json.dumps({"legacy_alias": "sk-legacy-map"}),
    )
    key, label = resolve_api_key()
    assert key == "sk-legacy-map"
    assert label == "per_bot:json_map:legacy_alias"


def test_per_bot_discrete_preferred_over_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MORPHEUS_KEY_MODE", "per_bot")
    monkeypatch.setenv("MORPHEUS_AGENT_SLOT", "ciso")
    monkeypatch.setenv("MORPHEUS_API_KEY_CISO", "sk-ciso-discrete")
    monkeypatch.setenv(
        "MORPHEUS_API_KEYS_JSON",
        json.dumps({"ciso": "sk-ciso-map"}),
    )
    key, label = resolve_api_key()
    assert key == "sk-ciso-discrete"
    assert "discrete" in label


def test_per_bot_hard_fail_no_silent_shared(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MORPHEUS_KEY_MODE", "per_bot")
    monkeypatch.setenv("MORPHEUS_AGENT_SLOT", "coo")
    monkeypatch.setenv("MORPHEUS_API_KEY", "sk-shared-must-not-fallback")
    monkeypatch.delenv("MORPHEUS_API_KEY_COO", raising=False)
    monkeypatch.delenv("MORPHEUS_API_KEYS_JSON", raising=False)
    with pytest.raises(ConfigError, match="per_bot key missing"):
        resolve_api_key()


def test_per_bot_missing_slot_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MORPHEUS_KEY_MODE", "per_bot")
    monkeypatch.delenv("MORPHEUS_AGENT_SLOT", raising=False)
    monkeypatch.delenv("MORPHEUS_AGENT", raising=False)
    with pytest.raises(ConfigError, match="requires MORPHEUS_AGENT"):
        resolve_api_key()


def test_master_slot_refuse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MORPHEUS_KEY_MODE", "per_bot")
    monkeypatch.setenv("MORPHEUS_AGENT_SLOT", "master")
    monkeypatch.setenv("MORPHEUS_API_KEY_MASTER", "sk-master-nope")
    with pytest.raises(ConfigError, match="refusing master"):
        resolve_api_key()


def test_master_usage_only_role_refuse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MORPHEUS_KEY_MODE", "shared")
    monkeypatch.setenv("MORPHEUS_API_KEY", "sk-something")
    monkeypatch.setenv("MORPHEUS_UPLINK_KEY_ROLE", "master_usage_only")
    with pytest.raises(ConfigError, match="master/usage-only"):
        resolve_api_key()


def test_key_role_master_refuse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MORPHEUS_KEY_MODE", "shared")
    monkeypatch.setenv("MORPHEUS_API_KEY", "sk-something")
    monkeypatch.setenv("MORPHEUS_KEY_ROLE", "master")
    with pytest.raises(ConfigError, match="master"):
        resolve_api_key()


@pytest.fixture(autouse=True)
def _clear_role_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MORPHEUS_UPLINK_KEY_ROLE", raising=False)
    monkeypatch.delenv("MORPHEUS_KEY_ROLE", raising=False)

