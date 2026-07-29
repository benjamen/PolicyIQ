"""LLM provider adapter, per docs/01-ARCHITECTURE.md's provider-adapter
pattern: a single interface, extraction/query-answering code never imports
a vendor SDK directly. No real provider is wired in this pass (no LLM API
key exists yet) - MockLLMProvider is what every test in this repo exercises.
A real provider (e.g. Groq, via LLM_PROVIDER/LLM_KEY config once added as
secrets) is a follow-up that implements this same Protocol.

Every fact the schema below produces carries a verbatim `source_quote` -
never page/paragraph_ref/document_id, which the pipeline stamps from the
Section's own OCR-derived coordinates (app/pipeline/sections.py), never
LLM-invented, per docs/05-AI-EXTRACTION-STRATEGY.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, Field, ValidationError


class LLMProvider(Protocol):
    def extract(self, *, prompt: str, section_text: str, schema: type[BaseModel]) -> str:
        """Returns raw JSON text conforming to `schema`."""
        ...

    def answer(self, *, query: str, context_chunks: list[str]) -> str:
        ...

    def embed(self, *, text: str) -> list[float]:
        ...


class MockLLMProvider:
    """Test double. `canned` is a list of (substring, json_response) pairs -
    the first entry whose substring appears in `section_text` wins. Raises
    if nothing matches, so a test can't silently pass on an unconfigured
    section."""

    def __init__(self, canned: list[tuple[str, str]]):
        self._canned = canned

    def extract(self, *, prompt: str, section_text: str, schema: type[BaseModel]) -> str:
        for substring, response in self._canned:
            if substring in section_text:
                return response
        raise ValueError(f"MockLLMProvider: no canned response matches section text: {section_text[:200]!r}")

    def answer(self, *, query: str, context_chunks: list[str]) -> str:
        raise NotImplementedError("MockLLMProvider.answer: not exercised this pass (search/Q&A is out of scope)")

    def embed(self, *, text: str) -> list[float]:
        raise NotImplementedError("MockLLMProvider.embed: not exercised this pass (embeddings are out of scope)")


class GradedFactExtract(BaseModel):
    """Feeds app.db.models.GradedFact. `raw_value` encoding by category:
    tpd_definition -> TpdBasis enum value string; trauma_conditions ->
    integer as string; premium_structure -> small JSON object
    {"basis": "level", "guaranteed": true}; waiver_of_premium -> "true"/
    "false"; automatic_benefits -> integer as string. occupation_restrictions
    is NOT a GradedFact category - it comes from EligibilityRuleExtract."""

    category: Literal[
        "tpd_definition",
        "trauma_conditions",
        "premium_structure",
        "waiver_of_premium",
        "automatic_benefits",
    ]
    raw_value: str
    confidence: float = Field(ge=0, le=1)
    source_quote: str


class EligibilityRuleExtract(BaseModel):
    """Feeds app.db.models.EligibilityRule. `occupation_category` is None
    for the general age/smoker-status window; set for an occupation-specific
    restriction row."""

    occupation_category: str | None = None
    smoker_status: Literal["smoker", "non_smoker", "any"] = "any"
    age_min: int
    age_max: int
    restriction_type: Literal["none", "loading", "exclusion"] = "none"
    note: str | None = None
    confidence: float = Field(ge=0, le=1)
    source_quote: str


class BenefitExtract(BaseModel):
    name: str
    description: str | None = None
    monetary_limit: float | None = None
    percentage_limit: float | None = None
    is_automatic: bool = False
    confidence: float = Field(ge=0, le=1)
    source_quote: str


class LimitExtract(BaseModel):
    limit_type: str
    amount: float
    currency: str = "NZD"
    confidence: float = Field(ge=0, le=1)
    source_quote: str


class ExclusionExtract(BaseModel):
    description: str
    confidence: float = Field(ge=0, le=1)
    source_quote: str


class DefinitionExtract(BaseModel):
    term: str
    definition_text: str
    source_quote: str


class WaitingPeriodExtract(BaseModel):
    applies_to: str
    days: int
    confidence: float = Field(ge=0, le=1)
    source_quote: str


class OptionalBenefitExtract(BaseModel):
    name: str
    description: str | None = None
    additional_premium: float | None = None
    source_quote: str


class SectionExtraction(BaseModel):
    graded_facts: list[GradedFactExtract] = Field(default_factory=list)
    eligibility_rules: list[EligibilityRuleExtract] = Field(default_factory=list)
    benefits: list[BenefitExtract] = Field(default_factory=list)
    limits: list[LimitExtract] = Field(default_factory=list)
    exclusions: list[ExclusionExtract] = Field(default_factory=list)
    definitions: list[DefinitionExtract] = Field(default_factory=list)
    waiting_periods: list[WaitingPeriodExtract] = Field(default_factory=list)
    optional_benefits: list[OptionalBenefitExtract] = Field(default_factory=list)


@dataclass(frozen=True)
class ExtractionFailure:
    """Typed failure, not a crash or silent drop - routes conceptually to
    an admin review queue (not built this pass, see docs/04's admin
    review-queue reference for classify() failures - same pattern)."""

    section_ref: str
    last_error: str
    attempts: int


def extract_with_retry(
    provider: LLMProvider,
    *,
    prompt: str,
    section_text: str,
    section_ref: str = "",
    max_retries: int = 2,
) -> SectionExtraction | ExtractionFailure:
    attempt = 0
    current_prompt = prompt
    last_error = ""

    while attempt <= max_retries:
        attempt += 1
        raw = provider.extract(prompt=current_prompt, section_text=section_text, schema=SectionExtraction)
        try:
            return SectionExtraction.model_validate_json(raw)
        except (ValidationError, ValueError) as exc:
            last_error = str(exc)
            current_prompt = f"{prompt}\n\nYour previous response was invalid: {last_error}\nRespond with valid JSON matching the schema."

    return ExtractionFailure(section_ref=section_ref, last_error=last_error, attempts=attempt)
