import json

import httpx
import pytest

from app.providers.llm import NvidiaProvider, SectionExtraction, get_provider

_VALID_CONTENT = json.dumps(
    {
        "graded_facts": [],
        "eligibility_rules": [],
        "benefits": [],
        "limits": [],
        "exclusions": [],
        "definitions": [],
        "waiting_periods": [],
        "optional_benefits": [],
    }
)


def _client_returning(status_code: int, json_body: dict) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=json_body, request=request)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_extract_sends_bearer_auth_json_mode_and_schema_to_the_nvidia_endpoint():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": _VALID_CONTENT}}]}, request=request
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = NvidiaProvider("nvapi-test-key", client=client)

    raw = provider.extract(prompt="Extract every benefit.", section_text="Section text here.", schema=SectionExtraction)

    assert raw == _VALID_CONTENT
    assert str(captured["request"].url) == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert captured["request"].headers["authorization"] == "Bearer nvapi-test-key"
    body = captured["body"]
    assert body["model"] == "meta/llama-3.3-70b-instruct"
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"][1]["content"] == "Section text here."


def test_non_200_response_raises_a_value_error_naming_the_provider():
    client = _client_returning(500, {"error": "server error"})
    provider = NvidiaProvider("nvapi-test-key", client=client)

    with pytest.raises(ValueError, match="NvidiaProvider: API returned 500"):
        provider.extract(prompt="p", section_text="s", schema=SectionExtraction)


def test_429_backoff_works_the_same_as_groq_via_the_shared_base_class():
    """NvidiaProvider shares _OpenAICompatibleChatProvider with GroqProvider
    - this proves the refactor didn't silently break the rate-limit
    backoff for the non-Groq subclass."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(
                429, json={"error": {"message": "Please try again in 3s."}}, request=request
            )
        return httpx.Response(200, json={"choices": [{"message": {"content": _VALID_CONTENT}}]}, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    sleeps = []
    provider = NvidiaProvider("nvapi-test-key", client=client, sleep=sleeps.append)

    raw = provider.extract(prompt="p", section_text="s", schema=SectionExtraction)

    assert raw == _VALID_CONTENT
    assert sleeps == [3.0]


def test_get_provider_uses_nvidia_llm_key_not_the_shared_llm_key(monkeypatch):
    """NVIDIA_LLM_KEY is a separate secret from Groq's LLM_KEY on purpose -
    both providers can stay configured side-by-side, and LLM_PROVIDER
    alone picks which one runs, without overwriting the other's key."""
    monkeypatch.setenv("LLM_PROVIDER", "nvidia")
    monkeypatch.setenv("NVIDIA_LLM_KEY", "nvapi-real-key")
    monkeypatch.setenv("LLM_KEY", "gsk-groq-key-should-not-be-used")
    monkeypatch.delenv("LLM_MODEL", raising=False)

    provider = get_provider()

    assert isinstance(provider, NvidiaProvider)
    assert provider._api_key == "nvapi-real-key"
    assert provider._model == "meta/llama-3.3-70b-instruct"


def test_get_provider_falls_back_to_llm_key_when_nvidia_llm_key_is_unset(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nvidia")
    monkeypatch.delenv("NVIDIA_LLM_KEY", raising=False)
    monkeypatch.setenv("LLM_KEY", "nvapi-test-key")

    provider = get_provider()

    assert isinstance(provider, NvidiaProvider)
    assert provider._api_key == "nvapi-test-key"


def test_get_provider_respects_llm_model_override_for_nvidia(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nvidia")
    monkeypatch.setenv("NVIDIA_LLM_KEY", "nvapi-test-key")
    monkeypatch.setenv("LLM_MODEL", "mistralai/mixtral-8x22b-instruct")

    provider = get_provider()

    assert isinstance(provider, NvidiaProvider)
    assert provider._model == "mistralai/mixtral-8x22b-instruct"
