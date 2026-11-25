from types import SimpleNamespace

import httpx
import pytest

from backend.app.llm_client import (
    LLMUnavailable,
    LocalOpenAIClient,
    OpenAIRouterClient,
    build_llm_client,
)


def decision_payload() -> dict:
    return {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"sense":"s","think":"t","act":"a","explain":"e",'
                        '"severity":"low","category":"prompt_injection",'
                        '"risk_level":"low","auto_execute":true}'
                    )
                }
            }
        ]
    }


class FakeResponse:
    def __init__(self, payload: dict | None = None, error: Exception | None = None) -> None:
        self._payload = payload if payload is not None else decision_payload()
        self._error = error

    def raise_for_status(self) -> None:
        if self._error is not None:
            raise self._error

    def json(self) -> dict:
        return self._payload


def router_settings() -> SimpleNamespace:
    return SimpleNamespace(
        ROUTER_BASE_URL="https://agentrouter.org/v1/",
        ROUTER_MODEL="gpt-5.6-sol",
        ROUTER_API_KEY="test-router-key",
        LLM_TIMEOUT_SECONDS=15.0,
    )


def test_router_client_posts_to_router_with_bearer_auth(monkeypatch) -> None:  # noqa: ANN001
    captured: dict = {}

    def fake_post(url: str, *, json: dict, headers: dict, timeout: float) -> FakeResponse:
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(httpx, "post", fake_post)

    client = OpenAIRouterClient(router_settings())  # type: ignore[arg-type]
    result = client.reason("telemetry prompt")

    assert captured["url"] == "https://agentrouter.org/v1/chat/completions"
    assert captured["headers"] == {"Authorization": "Bearer test-router-key"}
    assert captured["json"]["model"] == "gpt-5.6-sol"
    assert captured["json"]["messages"][0]["role"] == "system"
    assert captured["json"]["messages"][1] == {
        "role": "user",
        "content": "telemetry prompt",
    }
    assert captured["json"]["response_format"] == {"type": "json_object"}
    assert captured["timeout"] == 15.0
    assert result.category == "prompt_injection"


def test_router_failure_maps_to_llm_unavailable(monkeypatch) -> None:  # noqa: ANN001
    def fake_post(url: str, *, json: dict, headers: dict, timeout: float) -> FakeResponse:
        return FakeResponse(
            error=httpx.HTTPStatusError(
                "401 Unauthorized",
                request=httpx.Request("POST", url),
                response=httpx.Response(401),
            )
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = OpenAIRouterClient(router_settings())  # type: ignore[arg-type]

    with pytest.raises(LLMUnavailable, match="401 Unauthorized"):
        client.reason("telemetry prompt")


def test_local_client_appends_chat_completions(monkeypatch) -> None:  # noqa: ANN001
    captured: dict = {}

    def fake_post(url: str, *, json: dict, timeout: float) -> FakeResponse:
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(httpx, "post", fake_post)
    settings = SimpleNamespace(
        LOCAL_LLM_BASE_URL="http://127.0.0.1:11434/v1/",
        LOCAL_LLM_MODEL="local-model",
        LLM_TIMEOUT_SECONDS=12.0,
    )

    client = LocalOpenAIClient(settings)  # type: ignore[arg-type]
    result = client.reason("telemetry prompt")

    assert captured["url"] == "http://127.0.0.1:11434/v1/chat/completions"
    assert captured["json"]["model"] == "local-model"
    assert captured["json"]["response_format"] == {"type": "json_object"}
    assert captured["timeout"] == 12.0
    assert result.category == "prompt_injection"


def test_build_client_selects_provider() -> None:
    router = SimpleNamespace(
        LLM_PROVIDER="openai",
        ROUTER_BASE_URL="https://agentrouter.org/v1",
        ROUTER_MODEL="gpt-5.6-sol",
        ROUTER_API_KEY="k",
        LLM_TIMEOUT_SECONDS=30.0,
    )
    local = SimpleNamespace(
        LLM_PROVIDER="local",
        LOCAL_LLM_BASE_URL="http://127.0.0.1:11434/v1",
        LOCAL_LLM_MODEL="local-model",
        LLM_TIMEOUT_SECONDS=30.0,
    )

    assert isinstance(build_llm_client(router), OpenAIRouterClient)  # type: ignore[arg-type]
    assert isinstance(build_llm_client(local), LocalOpenAIClient)  # type: ignore[arg-type]
