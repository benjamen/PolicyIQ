"""LLM provider adapter, per docs/01-ARCHITECTURE.md's provider-adapter
pattern: a single interface, extraction/query-answering code never imports
a vendor SDK directly. MockLLMProvider is what every test in this repo
exercises. GroqProvider is the one real implementation - Groq's chat
completions API is OpenAI-compatible, so it's a plain httpx call (already
a dependency) rather than a new SDK. get_provider() wires it up from
LLM_PROVIDER/LLM_KEY/LLM_MODEL env vars, returning None (not a silent
mock/fallback) when unconfigured.

Every fact the schema below produces carries a verbatim `source_quote` -
never page/paragraph_ref/document_id, which the pipeline stamps from the
Section's own OCR-derived coordinates (app/pipeline/sections.py), never
LLM-invented, per docs/05-AI-EXTRACTION-STRATEGY.md.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Callable, Literal, Protocol

import httpx
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


# Both Groq and NVIDIA NIM's 429 bodies embed a human-readable wait hint,
# e.g. "Please try again in 13.25s." - real evidence from 2026-07-29: a
# 47-section real batch blew through Groq's free/on-demand tier's 12,000
# TPM budget after ~4 calls, and every retry thereafter hit the same
# still-exhausted window because nothing waited before retrying - 3
# instant attempts just fail 3 times in a row.
_RATE_LIMIT_WAIT_RE = re.compile(r"try again in (\d+(?:\.\d+)?)s", re.IGNORECASE)
_DEFAULT_RATE_LIMIT_WAIT_SECONDS = 15.0


class _OpenAICompatibleChatProvider:
    """Shared implementation for LLMProviders backed by an OpenAI-compatible
    chat completions endpoint - Groq and NVIDIA NIM both are, so this is
    the one real place the request/retry/parsing logic lives rather than
    duplicated per vendor. Subclasses set `_API_URL` and their own default
    model; everything else (JSON mode, rate-limit backoff, error handling)
    is identical.

    JSON mode (`response_format: json_object`) only guarantees the response
    is syntactically valid JSON, not that it matches `schema` - so the
    schema is spelled out in the system message, and the real enforcement
    stays where it already was: extract_with_retry()'s Pydantic validation
    + reprompt-on-failure loop. Every failure mode (network error, non-200
    response, malformed response body) is normalized to a ValueError so
    extract_with_retry's existing except clause handles it the same way it
    handles a schema-invalid response, rather than crashing the caller with
    an unhandled httpx exception.

    A 429 (rate limit) gets different treatment: it's retried *within* this
    call, actually waiting out the vendor's own hinted duration first -
    Groq's free/on-demand tier's per-minute token budget is small enough
    that a real multi-section batch hits it routinely, and retrying
    instantly (as extract_with_retry's outer loop does for every other
    failure) just re-hits the same still-exhausted window every time."""

    _API_URL: str = ""
    _PROVIDER_NAME: str = "LLMProvider"

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = 60.0,
        max_rate_limit_retries: int = 5,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._api_key = api_key
        self._model = model
        self._client = client or httpx.Client(timeout=timeout)
        self._max_rate_limit_retries = max_rate_limit_retries
        self._sleep = sleep

    def extract(self, *, prompt: str, section_text: str, schema: type[BaseModel]) -> str:
        system_message = (
            f"{prompt}\n\nRespond with valid JSON only, matching this JSON schema exactly:\n"
            f"{json.dumps(schema.model_json_schema())}"
        )
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": section_text},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

        for attempt in range(self._max_rate_limit_retries + 1):
            try:
                resp = self._client.post(self._API_URL, headers=headers, json=payload)
            except httpx.HTTPError as exc:
                raise ValueError(f"{self._PROVIDER_NAME}: request failed: {exc}") from exc

            if resp.status_code == 429 and attempt < self._max_rate_limit_retries:
                self._sleep(self._seconds_until_retry(resp))
                continue

            if resp.status_code != 200:
                raise ValueError(f"{self._PROVIDER_NAME}: API returned {resp.status_code}: {resp.text[:500]}")

            body = resp.json()
            try:
                return body["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as exc:
                raise ValueError(f"{self._PROVIDER_NAME}: unexpected response shape: {body}") from exc

        raise AssertionError("unreachable")  # loop always returns or raises above

    @staticmethod
    def _seconds_until_retry(resp: httpx.Response) -> float:
        retry_after = resp.headers.get("retry-after")
        if retry_after is not None:
            try:
                return float(retry_after)
            except ValueError:
                pass
        match = _RATE_LIMIT_WAIT_RE.search(resp.text)
        if match:
            return float(match.group(1))
        return _DEFAULT_RATE_LIMIT_WAIT_SECONDS

    def answer(self, *, query: str, context_chunks: list[str]) -> str:
        raise NotImplementedError(f"{self._PROVIDER_NAME}.answer: not exercised this pass (search/Q&A is out of scope)")

    def embed(self, *, text: str) -> list[float]:
        raise NotImplementedError(f"{self._PROVIDER_NAME}.embed: not exercised this pass (embeddings are out of scope)")


class GroqProvider(_OpenAICompatibleChatProvider):
    """Groq's chat completions API - see the base class docstring for the
    shared request/retry/parsing behaviour."""

    _API_URL = "https://api.groq.com/openai/v1/chat/completions"
    _PROVIDER_NAME = "GroqProvider"

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile", **kwargs):
        super().__init__(api_key, model, **kwargs)


class NvidiaProvider(_OpenAICompatibleChatProvider):
    """NVIDIA NIM's chat completions API (integrate.api.nvidia.com) - also
    OpenAI-compatible, added as an alternative to Groq's free-tier rate
    limits (see GroqProvider / groq-rate-limit-backoff in the policyiq-ops
    wiki). See the base class docstring for the shared request/retry/
    parsing behaviour."""

    _API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
    _PROVIDER_NAME = "NvidiaProvider"

    def __init__(self, api_key: str, model: str = "meta/llama-3.3-70b-instruct", **kwargs):
        super().__init__(api_key, model, **kwargs)


def get_provider() -> LLMProvider | None:
    """Reads LLM_PROVIDER/LLM_MODEL plus a provider-specific API key from
    the environment (see .env.example). Groq uses LLM_KEY; NVIDIA NIM uses
    NVIDIA_LLM_KEY (falling back to LLM_KEY if unset) - kept as separate
    secrets rather than one shared LLM_KEY so both providers can stay
    configured side-by-side and LLM_PROVIDER alone picks which one runs.
    Returns None - never a default/mock - when unconfigured, so callers
    (run_ingest.py) must handle "no provider" explicitly rather than
    silently extracting with something that can't handle real text."""
    provider_name = os.environ.get("LLM_PROVIDER")
    if not provider_name:
        return None
    model = os.environ.get("LLM_MODEL") or None
    if provider_name == "groq":
        api_key = os.environ.get("LLM_KEY")
        if not api_key:
            return None
        return GroqProvider(api_key, **({"model": model} if model else {}))
    if provider_name == "nvidia":
        api_key = os.environ.get("NVIDIA_LLM_KEY") or os.environ.get("LLM_KEY")
        if not api_key:
            return None
        return NvidiaProvider(api_key, **({"model": model} if model else {}))
    raise ValueError(f"Unknown LLM_PROVIDER: {provider_name!r} (supported: 'groq', 'nvidia')")


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

        try:
            raw = provider.extract(prompt=current_prompt, section_text=section_text, schema=SectionExtraction)
        except ValueError as exc:
            # A provider-level failure (network error, rate limit, bad
            # response shape) - not a schema-invalid response, so the prompt
            # isn't rewritten (the model never actually saw this attempt).
            last_error = str(exc)
            continue

        try:
            return SectionExtraction.model_validate_json(raw)
        except (ValidationError, ValueError) as exc:
            last_error = str(exc)
            current_prompt = f"{prompt}\n\nYour previous response was invalid: {last_error}\nRespond with valid JSON matching the schema."

    return ExtractionFailure(section_ref=section_ref, last_error=last_error, attempts=attempt)
