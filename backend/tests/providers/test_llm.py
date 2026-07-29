import json

from app.providers.llm import (
    ExtractionFailure,
    MockLLMProvider,
    SectionExtraction,
    extract_with_retry,
)

_VALID_RESPONSE = json.dumps(
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


def test_happy_path_returns_validated_extraction():
    provider = MockLLMProvider(canned=[("TPD Definition", _VALID_RESPONSE)])

    result = extract_with_retry(provider, prompt="extract facts", section_text="Section: TPD Definition...")

    assert isinstance(result, SectionExtraction)
    assert result.graded_facts[0].category == "tpd_definition"
    assert result.graded_facts[0].raw_value == "own_occupation"


def test_mock_provider_raises_on_unmatched_section():
    provider = MockLLMProvider(canned=[("TPD Definition", _VALID_RESPONSE)])

    try:
        provider.extract(prompt="x", section_text="Something unrelated entirely", schema=SectionExtraction)
        assert False, "expected ValueError"
    except ValueError:
        pass


class FlakyMockProvider:
    """Returns invalid JSON once, then a valid response - proves retry happens."""

    def __init__(self):
        self.calls = 0

    def extract(self, *, prompt, section_text, schema):
        self.calls += 1
        if self.calls == 1:
            return "not valid json at all"
        return _VALID_RESPONSE

    def answer(self, *, query, context_chunks):
        raise NotImplementedError

    def embed(self, *, text):
        raise NotImplementedError


def test_retries_once_then_succeeds():
    provider = FlakyMockProvider()

    result = extract_with_retry(provider, prompt="extract facts", section_text="anything", max_retries=2)

    assert isinstance(result, SectionExtraction)
    assert provider.calls == 2


class AlwaysInvalidProvider:
    def __init__(self):
        self.calls = 0

    def extract(self, *, prompt, section_text, schema):
        self.calls += 1
        return "still not valid json"

    def answer(self, *, query, context_chunks):
        raise NotImplementedError

    def embed(self, *, text):
        raise NotImplementedError


def test_exhausted_retries_returns_typed_failure_not_a_crash():
    provider = AlwaysInvalidProvider()

    result = extract_with_retry(
        provider, prompt="extract facts", section_text="anything", section_ref="doc-1/page-3", max_retries=2
    )

    assert isinstance(result, ExtractionFailure)
    assert result.section_ref == "doc-1/page-3"
    assert result.attempts == 3  # initial + 2 retries
