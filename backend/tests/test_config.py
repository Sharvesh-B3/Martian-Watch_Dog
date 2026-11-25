from pydantic import ValidationError
import pytest

from backend.app.config import Settings


def test_openai_provider_requires_router_config() -> None:
    with pytest.raises(ValidationError, match="ROUTER_API_KEY"):
        Settings(
            _env_file=None,
            LLM_PROVIDER="openai",
            ROUTER_BASE_URL="https://agentrouter.org/v1",
            ROUTER_MODEL="gpt-5.6-sol",
        )


def test_openai_provider_accepts_complete_config() -> None:
    settings = Settings(
        _env_file=None,
        LLM_PROVIDER="openai",
        ROUTER_BASE_URL="https://agentrouter.org/v1",
        ROUTER_MODEL="gpt-5.6-sol",
        ROUTER_API_KEY="test-router-key",
    )

    assert settings.LLM_PROVIDER == "openai"
    assert settings.ROUTER_MODEL == "gpt-5.6-sol"


def test_local_provider_requires_base_url() -> None:
    with pytest.raises(ValidationError, match="LOCAL_LLM_BASE_URL"):
        Settings(_env_file=None, LLM_PROVIDER="local")
