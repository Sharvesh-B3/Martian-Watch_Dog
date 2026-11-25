from pydantic import ValidationError
import pytest

from backend.app.config import Settings


def test_gemini_provider_requires_api_key() -> None:
    with pytest.raises(ValidationError, match="GEMINI_API_KEY"):
        Settings(_env_file=None, LLM_PROVIDER="gemini")


def test_gemini_provider_accepts_complete_config() -> None:
    settings = Settings(
        _env_file=None,
        LLM_PROVIDER="gemini",
        GEMINI_API_KEY="test-gemini-key",
    )

    assert settings.LLM_PROVIDER == "gemini"
    assert settings.GEMINI_MODEL == "gemini-3.5-flash-lite"


def test_gemini_model_is_configurable() -> None:
    settings = Settings(
        _env_file=None,
        GEMINI_API_KEY="test-gemini-key",
        GEMINI_MODEL="gemini-2.5-pro",
    )

    assert settings.GEMINI_MODEL == "gemini-2.5-pro"


def test_local_provider_requires_base_url() -> None:
    with pytest.raises(ValidationError, match="LOCAL_LLM_BASE_URL"):
        Settings(_env_file=None, LLM_PROVIDER="local")
