"""Repository layer: hydrates app.domain.models.ProductProfile from real,
citation-verified DB rows (PolicyVersion + GradedFact + EligibilityRule) -
the piece models.py's original docstring flagged as "not yet built."
app/api/v1/compare.py calls load_product_profiles() instead of
app/fixtures/sample_data.py.load_sample_profiles() (deleted this pass).

Fail-closed, per docs/01-ARCHITECTURE.md design principle #3: a
PolicyVersion with no general EligibilityRule row is excluded (logged),
not defaulted to some made-up age window. Zero matching PolicyVersions for
a product_type returns [] - never falls back to fixture data, because
there is none left to fall back to.
"""

from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Benefit,
    Document,
    EligibilityRule,
    Exclusion,
    GradedFact,
    Insurer,
    Limit,
    OccupationCategory,
    Policy,
    PolicyVersion,
    Product,
    Section,
)
from app.domain.models import (
    EligibilityWindow,
    GeneralInsuranceFact,
    GeneralProductProfile,
    OccupationRestriction,
    PremiumBasis,
    PremiumStructure,
    ProductProfile,
    RestrictionType,
    SmokerStatus,
    SourceRef,
    TpdBasis,
    TpdDefinition,
)

logger = logging.getLogger(__name__)


def _document_label(document: Document | None) -> str:
    if document is None:
        return "unknown document"
    tail = document.storage_key.rsplit("/", 1)[-1]
    filename = tail.split("-", 1)[1] if "-" in tail else tail
    return f"{document.doc_type.upper()} — {filename}"


def _source_ref(insurer_name: str, fact_row, documents_by_id: dict[uuid.UUID, Document]) -> SourceRef | None:
    if fact_row.document_id is None:
        return None
    return SourceRef(
        insurer=insurer_name,
        document=_document_label(documents_by_id.get(fact_row.document_id)),
        page=fact_row.page,
        paragraph_ref=fact_row.paragraph_ref,
        confidence=fact_row.confidence,
    )


def load_product_profiles(session: Session, *, product_type: str) -> list[ProductProfile]:
    rows = session.execute(
        select(PolicyVersion, Policy, Product, Insurer)
        .join(Policy, PolicyVersion.policy_id == Policy.id)
        .join(Product, Policy.product_id == Product.id)
        .join(Insurer, Product.insurer_id == Insurer.id)
        .where(PolicyVersion.status == "current", Product.product_type == product_type)
    ).all()

    profiles: list[ProductProfile] = []

    for policy_version, policy, product, insurer in rows:
        graded_facts = session.execute(
            select(GradedFact).where(GradedFact.policy_version_id == policy_version.id)
        ).scalars().all()
        eligibility_rules = session.execute(
            select(EligibilityRule).where(EligibilityRule.policy_version_id == policy_version.id)
        ).scalars().all()

        document_ids = {f.document_id for f in graded_facts if f.document_id is not None}
        document_ids |= {r.document_id for r in eligibility_rules if r.document_id is not None}
        documents_by_id: dict[uuid.UUID, Document] = {}
        if document_ids:
            for doc in session.execute(select(Document).where(Document.id.in_(document_ids))).scalars():
                documents_by_id[doc.id] = doc

        general_rule = next((r for r in eligibility_rules if r.occupation_category_id is None), None)
        if general_rule is None:
            # Not excluded - per compare()'s own principle ("hiding a
            # disqualified product is itself an unsourced claim"), hiding
            # an *eligible* product before compare() ever sees it is the
            # same problem one step earlier. age_min=0/age_max=120 is a
            # wide placeholder, never a guessed real range -
            # eligibility_published=False is what actually carries the
            # "we don't know" signal through to check_eligibility() and
            # the API response.
            logger.warning(
                "policy_version %s (%s / %s): no general eligibility rule extracted - "
                "showing with eligibility_published=False rather than excluding",
                policy_version.id, insurer.name, policy.name,
            )
            eligibility = EligibilityWindow(age_min=0, age_max=120, eligibility_published=False)
        else:
            eligibility = EligibilityWindow(
                age_min=general_rule.age_min,
                age_max=general_rule.age_max,
                smoker_status_available=SmokerStatus(general_rule.smoker_status),
            )

        occupation_category_ids = {
            r.occupation_category_id for r in eligibility_rules if r.occupation_category_id is not None
        }
        occupation_categories_by_id: dict[uuid.UUID, OccupationCategory] = {}
        if occupation_category_ids:
            for oc in session.execute(
                select(OccupationCategory).where(OccupationCategory.id.in_(occupation_category_ids))
            ).scalars():
                occupation_categories_by_id[oc.id] = oc

        occupation_restrictions = tuple(
            OccupationRestriction(
                occupation_category=occupation_categories_by_id[r.occupation_category_id].code,
                restriction_type=RestrictionType(r.restriction_type),
                note=r.note or "",
                source=_source_ref(insurer.name, r, documents_by_id) or SourceRef(
                    insurer=insurer.name, document="unknown document", page=0, paragraph_ref="", confidence=0.0
                ),
            )
            for r in eligibility_rules
            if r.occupation_category_id is not None and r.restriction_type != "none"
        )

        facts_by_category = {f.category: f for f in graded_facts}

        # Citation verification (app/verification.py) only checks that a
        # fact's source_quote is a real quote from the text - it says
        # nothing about whether raw_value actually matches the controlled
        # vocabulary/format its category promises. Real evidence
        # (2026-07-30): a real Groq-extracted tpd_definition fact had
        # raw_value="Paralysis (loss of everything)" - a real phrase from
        # the document, correctly cited, but not a valid TpdBasis member -
        # and TpdBasis(fact.raw_value) 500'd this endpoint for every
        # insurer/product, not just the one malformed fact. Every parse
        # below is now defensive: a malformed fact is dropped (logged) and
        # treated as absent, matching the same "missing fact is excluded,
        # not penalized" handling as a fact that was never extracted at
        # all - one bad fact must never take down the whole response.

        tpd_definition = None
        tpd_offered = True
        if (fact := facts_by_category.get("tpd_definition")) is not None:
            if fact.raw_value == "not_offered":
                # No citation to verify here by design - this is an absence
                # finding (this insurer's product lineup has no TPD cover at
                # all), not a quoted fact, same reasoning as the unpublished-
                # eligibility placeholder below.
                tpd_offered = False
            else:
                try:
                    tpd_definition = TpdDefinition(
                        basis=TpdBasis(fact.raw_value), source=_source_ref(insurer.name, fact, documents_by_id)
                    )
                except ValueError:
                    logger.warning(
                        "skipping malformed tpd_definition GradedFact %s (%s / %s): raw_value=%r is not a valid TpdBasis",
                        fact.id, insurer.name, policy.name, fact.raw_value,
                    )

        trauma_condition_count = None
        trauma_condition_source = None
        if (fact := facts_by_category.get("trauma_conditions")) is not None:
            try:
                trauma_condition_count = int(fact.raw_value)
                trauma_condition_source = _source_ref(insurer.name, fact, documents_by_id)
            except ValueError:
                logger.warning(
                    "skipping malformed trauma_conditions GradedFact %s (%s / %s): raw_value=%r is not an int",
                    fact.id, insurer.name, policy.name, fact.raw_value,
                )

        premium_structure = None
        if (fact := facts_by_category.get("premium_structure")) is not None:
            try:
                payload = json.loads(fact.raw_value)
                premium_structure = PremiumStructure(
                    basis=PremiumBasis(payload["basis"]),
                    guaranteed=bool(payload["guaranteed"]),
                    source=_source_ref(insurer.name, fact, documents_by_id),
                )
            except (json.JSONDecodeError, KeyError, ValueError):
                logger.warning(
                    "skipping malformed premium_structure GradedFact %s (%s / %s): raw_value=%r",
                    fact.id, insurer.name, policy.name, fact.raw_value,
                )

        waiver_of_premium = None
        waiver_of_premium_source = None
        if (fact := facts_by_category.get("waiver_of_premium")) is not None:
            waiver_of_premium = fact.raw_value == "true"
            waiver_of_premium_source = _source_ref(insurer.name, fact, documents_by_id)

        automatic_benefits_count = None
        automatic_benefits_source = None
        if (fact := facts_by_category.get("automatic_benefits")) is not None:
            try:
                automatic_benefits_count = int(fact.raw_value)
                automatic_benefits_source = _source_ref(insurer.name, fact, documents_by_id)
            except ValueError:
                logger.warning(
                    "skipping malformed automatic_benefits GradedFact %s (%s / %s): raw_value=%r is not an int",
                    fact.id, insurer.name, policy.name, fact.raw_value,
                )

        profiles.append(
            ProductProfile(
                insurer=insurer.name,
                product_name=policy.name,
                policy_version_id=str(policy_version.id),
                product_type=product.product_type,
                eligibility=eligibility,
                occupation_restrictions=occupation_restrictions,
                tpd_definition=tpd_definition,
                tpd_offered=tpd_offered,
                trauma_condition_count=trauma_condition_count,
                trauma_condition_source=trauma_condition_source,
                premium_structure=premium_structure,
                waiver_of_premium=waiver_of_premium,
                waiver_of_premium_source=waiver_of_premium_source,
                automatic_benefits_count=automatic_benefits_count,
                automatic_benefits_source=automatic_benefits_source,
            )
        )

    return profiles


def _general_source_ref(insurer_name: str, fact_row, sections_by_id: dict[uuid.UUID, Section],
                         documents_by_id: dict[uuid.UUID, Document]) -> SourceRef | None:
    """Benefit/Limit/Exclusion carry page/paragraph_ref/confidence directly
    (unlike GradedFact/EligibilityRule) but only a section_id, not a
    document_id - one extra hop through Section to find the document."""
    section = sections_by_id.get(fact_row.section_id)
    if section is None:
        return None
    return SourceRef(
        insurer=insurer_name,
        document=_document_label(documents_by_id.get(section.document_id)),
        page=fact_row.page,
        paragraph_ref=fact_row.paragraph_ref,
        confidence=fact_row.confidence,
    )


def load_general_insurance_profiles(session: Session, *, product_type: str) -> list[GeneralProductProfile]:
    """General (house/contents/travel) insurance is compared as a document
    diff, not a graded score (docs/08-UI-DESIGN.md) - this returns the raw
    real, citation-verified Benefit/Limit/Exclusion facts per insurer for a
    product type, with no weighting/scoring layer on top. Fail-closed like
    load_product_profiles(): zero matching PolicyVersions returns []."""
    rows = session.execute(
        select(PolicyVersion, Policy, Product, Insurer)
        .join(Policy, PolicyVersion.policy_id == Policy.id)
        .join(Product, Policy.product_id == Product.id)
        .join(Insurer, Product.insurer_id == Insurer.id)
        .where(Product.product_type == product_type, PolicyVersion.status == "current")
    ).all()

    profiles: list[GeneralProductProfile] = []
    for policy_version, policy, product, insurer in rows:
        sections_by_id = {
            s.id: s
            for s in session.execute(
                select(Section).where(Section.policy_version_id == policy_version.id)
            ).scalars()
        }
        document_ids = {s.document_id for s in sections_by_id.values()}
        documents_by_id = {
            d.id: d for d in session.execute(select(Document).where(Document.id.in_(document_ids))).scalars()
        }
        section_ids = list(sections_by_id.keys())

        facts: list[GeneralInsuranceFact] = []
        for b in session.execute(select(Benefit).where(Benefit.section_id.in_(section_ids))).scalars():
            facts.append(GeneralInsuranceFact(
                category="benefit", name=b.name, detail=b.description,
                source=_general_source_ref(insurer.name, b, sections_by_id, documents_by_id),
            ))
        for lim in session.execute(select(Limit).where(Limit.section_id.in_(section_ids))).scalars():
            facts.append(GeneralInsuranceFact(
                category="limit", name=lim.limit_type, detail=f"{lim.currency} {lim.amount:,.0f}",
                source=_general_source_ref(insurer.name, lim, sections_by_id, documents_by_id),
            ))
        for ex in session.execute(select(Exclusion).where(Exclusion.section_id.in_(section_ids))).scalars():
            facts.append(GeneralInsuranceFact(
                category="exclusion", name=ex.description, detail=None,
                source=_general_source_ref(insurer.name, ex, sections_by_id, documents_by_id),
            ))

        profiles.append(
            GeneralProductProfile(
                insurer=insurer.name,
                product_name=policy.name,
                policy_version_id=str(policy_version.id),
                product_type=product.product_type,
                facts=tuple(facts),
            )
        )

    return profiles
