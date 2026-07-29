import json

import httpx
import pytest

from app.providers.llm import GroqProvider, SectionExtraction, extract_with_retry, get_provider

_VALID_CONTENT = json.dumps(
    {
        "graded_facts": [
            {
                "category": "tpd_definition",
                "raw_value": "own_occupation",
                "confidence": 0.9,
                "source_quote": "TPD means own occupation basis",
            }
        ],
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


def test_extract_sends_bearer_auth_json_mode_and_schema_then_returns_content():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": _VALID_CONTENT}}]},
            request=request,
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = GroqProvider("test-key", model="llama-3.3-70b-versatile", client=client)

    raw = provider.extract(prompt="Extract every benefit.", section_text="Section text here.", schema=SectionExtraction)

    assert raw == _VALID_CONTENT
    assert captured["request"].headers["authorization"] == "Bearer test-key"
    body = captured["body"]
    assert body["model"] == "llama-3.3-70b-versatile"
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"][1]["content"] == "Section text here."
    assert "Extract every benefit." in body["messages"][0]["content"]
    assert "properties" in body["messages"][0]["content"]  # schema was included


def test_non_200_response_raises_value_error_not_a_crash():
    client = _client_returning(429, {"error": "rate limited"})
    provider = GroqProvider("test-key", client=client)

    with pytest.raises(ValueError, match="429"):
        provider.extract(prompt="p", section_text="s", schema=SectionExtraction)


def test_malformed_response_body_raises_value_error():
    client = _client_returning(200, {"unexpected": "shape"})
    provider = GroqProvider("test-key", client=client)

    with pytest.raises(ValueError, match="unexpected response shape"):
        provider.extract(prompt="p", section_text="s", schema=SectionExtraction)


def test_transport_error_is_normalized_to_value_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = GroqProvider("test-key", client=client)

    with pytest.raises(ValueError, match="request to Groq API failed"):
        provider.extract(prompt="p", section_text="s", schema=SectionExtraction)


def test_extract_with_retry_treats_a_groq_failure_like_any_other_provider_failure():
    """GroqProvider errors funnel into the same ValueError path
    extract_with_retry already handles - proves it degrades to a typed
    ExtractionFailure, not an unhandled exception, exactly like a
    schema-invalid response from any other provider."""
    client = _client_returning(500, {"error": "server error"})
    provider = GroqProvider("test-key", client=client)

    result = extract_with_retry(provider, prompt="p", section_text="s", section_ref="doc-1", max_retries=1)

    from app.providers.llm import ExtractionFailure

    assert isinstance(result, ExtractionFailure)
    assert result.attempts == 2


def test_get_provider_returns_none_when_unconfigured(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_KEY", raising=False)

    assert get_provider() is None


def test_get_provider_returns_groq_provider_when_configured(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_KEY", "sk-test")
    monkeypatch.setenv("LLM_MODEL", "llama-3.1-8b-instant")

    provider = get_provider()

    assert isinstance(provider, GroqProvider)
    assert provider._model == "llama-3.1-8b-instant"


def test_get_provider_rejects_unknown_provider_name(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "not-a-real-provider")
    monkeypatch.setenv("LLM_KEY", "sk-test")

    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        get_provider()
