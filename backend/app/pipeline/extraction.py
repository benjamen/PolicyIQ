"""Extraction orchestrator: per Section, calls the LLM provider, verifies
every claimed fact's citation against the Section's own parsed text, and
persists only verified facts. This is where "never hallucinate" actually
gets enforced mechanically (docs/05-AI-EXTRACTION-STRATEGY.md) - a fact
whose source_quote doesn't verify is dropped and counted, never persisted."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.db.models import (
    Benefit,
    Definition,
    EligibilityRule,
    Exclusion,
    GradedFact,
    Limit,
    OptionalBenefit,
    Section,
    WaitingPeriod,
)
from app.ocr.types import ParsedDocument
from app.providers.llm import ExtractionFailure, LLMProvider, extract_with_retry
from app.verification import verify_citation

DEFAULT_EXTRACTION_PROMPT = (
    "Extract every benefit, limit, exclusion, definition, waiting period, optional benefit, "
    "eligibility rule, and life-insurance grading fact (TPD definition, trauma condition count, "
    "premium structure, waiver of premium, automatic benefits count) explicitly stated in this "
    "section. For every item, include a verbatim source_quote copied exactly from the section "
    "text - never paraphrase the quote. Do not invent facts not stated in the text."
)


@dataclass
class SectionExtractionOutcome:
    section_id: uuid.UUID
    persisted_counts: dict[str, int] = field(default_factory=dict)
    rejected_counts: dict[str, int] = field(default_factory=dict)
    failure: ExtractionFailure | None = None


def process_section(
    session: Session,
    provider: LLMProvider,
    *,
    policy_version_id: uuid.UUID,
    document_id: uuid.UUID,
    section: Section,
    parsed_document: ParsedDocument,
    prompt: str = DEFAULT_EXTRACTION_PROMPT,
) -> SectionExtractionOutcome:
    section_text = parsed_document.page(section.page_start).text if parsed_document.page(section.page_start) else ""
    result = extract_with_retry(provider, prompt=prompt, section_text=section_text, section_ref=str(section.id))

    outcome = SectionExtractionOutcome(section_id=section.id)
    if isinstance(result, ExtractionFailure):
        outcome.failure = result
        return outcome

    page = section.page_start
    paragraph_ref = section.paragraph_ref or f"{page}.1"

    def _verified(quote: str) -> bool:
        return verify_citation(parsed_document, page=page, claimed_quote=quote).verified

    def _track(key: str, ok: bool) -> None:
        bucket = outcome.persisted_counts if ok else outcome.rejected_counts
        bucket[key] = bucket.get(key, 0) + 1

    for gf in result.graded_facts:
        ok = _verified(gf.source_quote)
        _track("graded_facts", ok)
        if ok:
            session.add(GradedFact(
                policy_version_id=policy_version_id, category=gf.category, raw_value=gf.raw_value,
                document_id=document_id, page=page, paragraph_ref=paragraph_ref, confidence=gf.confidence,
            ))

    for er in result.eligibility_rules:
        ok = _verified(er.source_quote)
        _track("eligibility_rules", ok)
        if ok:
            session.add(EligibilityRule(
                policy_version_id=policy_version_id, occupation_category_id=None,
                smoker_status=er.smoker_status, age_min=er.age_min, age_max=er.age_max,
                restriction_type=er.restriction_type, note=er.note,
                document_id=document_id, page=page, paragraph_ref=paragraph_ref, confidence=er.confidence,
            ))

    for b in result.benefits:
        ok = _verified(b.source_quote)
        _track("benefits", ok)
        if ok:
            session.add(Benefit(
                section_id=section.id, name=b.name, description=b.description,
                monetary_limit=b.monetary_limit, percentage_limit=b.percentage_limit,
                is_automatic=b.is_automatic, page=page, paragraph_ref=paragraph_ref, confidence=b.confidence,
            ))

    for lim in result.limits:
        ok = _verified(lim.source_quote)
        _track("limits", ok)
        if ok:
            session.add(Limit(
                section_id=section.id, limit_type=lim.limit_type, amount=lim.amount, currency=lim.currency,
                page=page, paragraph_ref=paragraph_ref, confidence=lim.confidence,
            ))

    for exc in result.exclusions:
        ok = _verified(exc.source_quote)
        _track("exclusions", ok)
        if ok:
            session.add(Exclusion(
                section_id=section.id, description=exc.description,
                page=page, paragraph_ref=paragraph_ref, confidence=exc.confidence,
            ))

    for d in result.definitions:
        ok = _verified(d.source_quote)
        _track("definitions", ok)
        if ok:
            session.add(Definition(
                section_id=section.id, term=d.term, definition_text=d.definition_text,
                page=page, paragraph_ref=paragraph_ref,
            ))

    for wp in result.waiting_periods:
        ok = _verified(wp.source_quote)
        _track("waiting_periods", ok)
        if ok:
            session.add(WaitingPeriod(
                section_id=section.id, applies_to=wp.applies_to, days=wp.days,
                page=page, paragraph_ref=paragraph_ref, confidence=wp.confidence,
            ))

    for ob in result.optional_benefits:
        ok = _verified(ob.source_quote)
        _track("optional_benefits", ok)
        if ok:
            session.add(OptionalBenefit(
                section_id=section.id, name=ob.name, description=ob.description,
                additional_premium=ob.additional_premium, page=page, paragraph_ref=paragraph_ref,
            ))

    session.flush()
    return outcome
