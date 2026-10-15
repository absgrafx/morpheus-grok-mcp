import pytest

VARS = ("MORPHEUS_API_KEY", "MORPHEUS_MODE", "MORPHEUS_BASE_URL", "MORPHEUS_MODELS")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for v in VARS:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("MORPHEUS_API_KEY", "sk-test0000000000secret")
    yield


@pytest.fixture
def anyio_backend():
    return "asyncio"
