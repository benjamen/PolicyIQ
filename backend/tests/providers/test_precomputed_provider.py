import json

from app.providers.llm import PrecomputedProvider, SectionExtraction, extract_with_retry

_VALID_RESPONSE = json.dumps(
    {
        "graded_facts": [],
        "eligibility_rules": [],
        "benefits": [
            {
                "name": "Life Cover",
                "description": "Pays a lump sum on death.",
                "monetary_limit": 500000.0,
                "percentage_limit": None,
                "is_automatic": True,
                "confidence": 1.0,
                "source_quote": "We will pay a lump sum on death.",
            }
        ],
        "limits": [],
        "exclusions": [],
        "definitions": [],
        "waiting_periods": [],
        "optional_benefits": [],
    }
)


def test_extract_returns_the_authored_extraction_for_matching_section_text():
    section_text = "Life Cover: We will pay a lump sum on death."
    key = PrecomputedProvider.section_key(section_text)
    provider = PrecomputedProvider({key: _VALID_RESPONSE})

    raw = provider.extract(prompt="extract facts", section_text=section_text, schema=SectionExtraction)

    assert raw == _VALID_RESPONSE


def test_extract_works_through_extract_with_retry_like_any_other_provider():
    section_text = "Life Cover: We will pay a lump sum on death."
    key = PrecomputedProvider.section_key(section_text)
    provider = PrecomputedProvider({key: _VALID_RESPONSE})

    result = extract_with_retry(provider, prompt="extract facts", section_text=section_text)

    assert isinstance(result, SectionExtraction)
    assert result.benefits[0].name == "Life Cover"


def test_raises_fail_closed_when_no_authored_extraction_matches():
    """A section with no authored entry yet must be a visible gap, not a
    silently empty result - same fail-closed contract as MockLLMProvider
    raising on an unmatched canned response."""
    provider = PrecomputedProvider({})

    try:
        provider.extract(prompt="x", section_text="Some section nobody has authored yet", schema=SectionExtraction)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "no authored extraction" in str(exc)


def test_section_key_is_a_stable_deterministic_hash():
    assert PrecomputedProvider.section_key("same text") == PrecomputedProvider.section_key("same text")
    assert PrecomputedProvider.section_key("text a") != PrecomputedProvider.section_key("text b")
