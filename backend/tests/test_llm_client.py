from types import SimpleNamespace

import httpx
import pytest

from backend.app.llm_client import (
    GeminiClient,
    LLMUnavailable,
    LocalOpenAIClient,
    build_llm_client,
)


def decision_text() -> str:
    return (
        '{"sense":"s","think":"t","act":"a","explain":"e",'
        '"severity":"low","category":"prompt_injection",'
        '"risk_level":"low","auto_execute":true}'
    )


def decision_payload() -> dict:
    return {"choices": [{"message": {"content": decision_text()}}]}


def gemini_payload(
    text: str | None = None, *, include_thought: bool = False
) -> dict:
    parts: list[dict] = []
    if include_thought:
        parts.append({"text": "internal reasoning", "thought": True})
    parts.append({"text": text or decision_text()})
    return {
        "candidates": [
            {
                "content": {"role": "model", "parts": parts},
                "finishReason": "STOP",
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


def gemini_settings() -> SimpleNamespace:
    return SimpleNamespace(
        GEMINI_API_KEY="test-gemini-key",
        GEMINI_MODEL="gemini-3.5-flash-lite",
        LLM_TIMEOUT_SECONDS=15.0,
    )


def test_gemini_client_posts_to_generate_content_with_api_key(monkeypatch) -> None:  # noqa: ANN001
    captured: dict = {}

    def fake_post(url: str, *, json: dict, headers: dict, timeout: float) -> FakeResponse:
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse(gemini_payload())

    monkeypatch.setattr(httpx, "post", fake_post)

    client = GeminiClient(gemini_settings())  # type: ignore[arg-type]
    result = client.reason("telemetry prompt")

    assert captured["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-3.5-flash-lite:generateContent"
    )
    assert captured["headers"]["x-goog-api-key"] == "test-gemini-key"
    assert "Authorization" not in captured["headers"]
    assert "Return ONLY a JSON object" in captured["json"]["systemInstruction"]["parts"][0]["text"]
    assert captured["json"]["contents"] == [
        {"role": "user", "parts": [{"text": "telemetry prompt"}]}
    ]
    generation_config = captured["json"]["generationConfig"]
    assert generation_config["responseMimeType"] == "application/json"
    assert "auto_execute" in generation_config["responseSchema"]["required"]
    assert captured["timeout"] == 15.0
    assert result.category == "prompt_injection"


def test_gemini_client_skips_thought_parts(monkeypatch) -> None:  # noqa: ANN001
    def fake_post(url: str, *, json: dict, headers: dict, timeout: float) -> FakeResponse:
        return FakeResponse(gemini_payload(include_thought=True))

    monkeypatch.setattr(httpx, "post", fake_post)

    result = GeminiClient(gemini_settings()).reason("telemetry prompt")  # type: ignore[arg-type]

    assert result.sense == "s"
    assert result.auto_execute is True


def test_gemini_client_accepts_fenced_json(monkeypatch) -> None:  # noqa: ANN001
    def fake_post(url: str, *, json: dict, headers: dict, timeout: float) -> FakeResponse:
        return FakeResponse(gemini_payload(f"```json\n{decision_text()}\n```"))

    monkeypatch.setattr(httpx, "post", fake_post)

    result = GeminiClient(gemini_settings()).reason("telemetry prompt")  # type: ignore[arg-type]

    assert result.category == "prompt_injection"


def test_gemini_failure_maps_to_llm_unavailable(monkeypatch) -> None:  # noqa: ANN001
    def fake_post(url: str, *, json: dict, headers: dict, timeout: float) -> FakeResponse:
        return FakeResponse(
            error=httpx.HTTPStatusError(
                "401 Unauthorized",
                request=httpx.Request("POST", url),
                response=httpx.Response(401),
            )
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = GeminiClient(gemini_settings())  # type: ignore[arg-type]

    with pytest.raises(LLMUnavailable, match="401 Unauthorized"):
        client.reason("telemetry prompt")


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"candidates": []}, "no candidates"),
        ({"promptFeedback": {"blockReason": "SAFETY"}}, "blockReason=SAFETY"),
        (gemini_payload("not json"), "Gemini LLM reasoning failed"),
    ],
)
def test_gemini_invalid_response_maps_to_llm_unavailable(
    monkeypatch, payload: dict, message: str
) -> None:  # noqa: ANN001
    def fake_post(url: str, *, json: dict, headers: dict, timeout: float) -> FakeResponse:
        return FakeResponse(payload)

    monkeypatch.setattr(httpx, "post", fake_post)
    client = GeminiClient(gemini_settings())  # type: ignore[arg-type]

    with pytest.raises(LLMUnavailable, match=message):
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
    gemini = SimpleNamespace(
        LLM_PROVIDER="gemini",
        GEMINI_API_KEY="k",
        GEMINI_MODEL="gemini-3.5-flash-lite",
        LLM_TIMEOUT_SECONDS=30.0,
    )
    local = SimpleNamespace(
        LLM_PROVIDER="local",
        LOCAL_LLM_BASE_URL="http://127.0.0.1:11434/v1",
        LOCAL_LLM_MODEL="local-model",
        LLM_TIMEOUT_SECONDS=30.0,
    )

    assert isinstance(build_llm_client(gemini), GeminiClient)  # type: ignore[arg-type]
    assert isinstance(build_llm_client(local), LocalOpenAIClient)  # type: ignore[arg-type]
