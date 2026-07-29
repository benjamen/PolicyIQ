"""SQLAlchemy models for PolicyIQ's document pipeline + life-insurance schema.

Two layers on top of the core ERD in docs/02-DATABASE-ERD.md:

1. The document/extraction schema (Policy, Document, Section, Benefit, Limit,
   Exclusion, Definition, WaitingPeriod, OptionalBenefit) - what the real
   crawler -> downloader -> OCR -> LLM-extraction -> citation-verification
   pipeline (docs/04, docs/05) actually populates.
2. The life-insurance grading extension (occupation_category, eligibility_rule,
   graded_fact) - purpose-built extraction output feeding the deterministic
   grading engine (app/services/grading.py), written alongside the generic
   Section-scoped facts above, not derived from them (see the repository
   layer in app/db/repository.py for why).

`policy_version.policy_id` replaces `policy_version.product_id` as of this
pass - a direct, non-additive schema change (dropping a column rather than
the usual additive-first convention from docs/06-DEPLOYMENT-PLAN.md), safe
only because no production data exists yet.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator, CHAR


class GUID(TypeDecorator):
    """Portable UUID column: native UUID on Postgres, CHAR(36) elsewhere (sqlite
    for local/CI tests, per docs/06-DEPLOYMENT-PLAN.md's local-env compose)."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID

            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return uuid.UUID(str(value))


class Base(DeclarativeBase):
    pass


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Insurer(Base):
    __tablename__ = "insurer"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    website_root: Mapped[str] = mapped_column(String(255))
    crawl_policy_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Product(Base):
    __tablename__ = "product"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=_uuid)
    insurer_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("insurer.id"))
    vertical: Mapped[str] = mapped_column(String(40), default="insurance")
    product_type: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(160))


class Policy(Base):
    """One named policy offered by an insurer (e.g. AMI's "House Policy").
    Sits between Product and PolicyVersion per the ERD - a Product (e.g.
    "home insurance") can have multiple named Policies over time."""

    __tablename__ = "policy"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=_uuid)
    product_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("product.id"))
    name: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PolicyVersion(Base):
    __tablename__ = "policy_version"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=_uuid)
    policy_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("policy.id"))
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="current")
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Document(Base):
    """One downloaded, content-addressed PDF - the Downloader's output
    (app/pipeline/downloader.py). `storage_key` follows the scheme in
    docs/04-CRAWLER-STRATEGY.md; `sha256_hash` is what makes "never
    overwrite" a structural property rather than a runtime check."""

    __tablename__ = "document"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=_uuid)
    policy_version_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("policy_version.id"))
    doc_type: Mapped[str] = mapped_column(String(30))
    # Not unique: two Document rows (different policy_version/source_url) can
    # legitimately share a storage_key when they're the same bytes reused
    # across URLs - see app/pipeline/downloader.py's dedup-by-hash path.
    storage_key: Mapped[str] = mapped_column(String(500))
    sha256_hash: Mapped[str] = mapped_column(String(64), index=True)
    etag: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_modified: Mapped[str | None] = mapped_column(String(80), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_url: Mapped[str] = mapped_column(String(1000))
    downloaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Section(Base):
    """Join point between document structure (page/paragraph location) and
    every extracted-fact table below - see docs/02-DATABASE-ERD.md's notes
    on why Section exists. Phase 1: one Section per PDF page
    (app/pipeline/sections.py) - real heading-detection is future work."""

    __tablename__ = "section"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=_uuid)
    policy_version_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("policy_version.id"))
    document_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("document.id"))
    heading: Mapped[str | None] = mapped_column(String(300), nullable=True)
    page_start: Mapped[int] = mapped_column(Integer)
    page_end: Mapped[int] = mapped_column(Integer)
    paragraph_ref: Mapped[str | None] = mapped_column(String(40), nullable=True)


class Benefit(Base):
    __tablename__ = "benefit"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=_uuid)
    section_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("section.id"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    monetary_limit: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    percentage_limit: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    is_automatic: Mapped[bool] = mapped_column(Boolean, default=False)
    page: Mapped[int] = mapped_column(Integer)
    paragraph_ref: Mapped[str] = mapped_column(String(40))
    confidence: Mapped[float] = mapped_column(Float)


class Limit(Base):
    """Table name `policy_limit`, not `limit` - `limit` is a reserved word in
    Postgres/SQL. Class name stays `Limit` for fidelity to the ERD label."""

    __tablename__ = "policy_limit"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=_uuid)
    section_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("section.id"))
    limit_type: Mapped[str] = mapped_column(String(60))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="NZD")
    page: Mapped[int] = mapped_column(Integer)
    paragraph_ref: Mapped[str] = mapped_column(String(40))
    confidence: Mapped[float] = mapped_column(Float)


class Exclusion(Base):
    __tablename__ = "exclusion"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=_uuid)
    section_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("section.id"))
    description: Mapped[str] = mapped_column(Text)
    page: Mapped[int] = mapped_column(Integer)
    paragraph_ref: Mapped[str] = mapped_column(String(40))
    confidence: Mapped[float] = mapped_column(Float)


class Definition(Base):
    __tablename__ = "definition"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=_uuid)
    section_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("section.id"))
    term: Mapped[str] = mapped_column(String(200))
    definition_text: Mapped[str] = mapped_column(Text)
    page: Mapped[int] = mapped_column(Integer)
    paragraph_ref: Mapped[str] = mapped_column(String(40))


class WaitingPeriod(Base):
    __tablename__ = "waiting_period"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=_uuid)
    section_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("section.id"))
    applies_to: Mapped[str] = mapped_column(String(200))
    days: Mapped[int] = mapped_column(Integer)
    page: Mapped[int] = mapped_column(Integer)
    paragraph_ref: Mapped[str] = mapped_column(String(40))
    confidence: Mapped[float] = mapped_column(Float)


class OptionalBenefit(Base):
    __tablename__ = "optional_benefit"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=_uuid)
    section_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("section.id"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    additional_premium: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    page: Mapped[int] = mapped_column(Integer)
    paragraph_ref: Mapped[str] = mapped_column(String(40))


class OccupationCategory(Base):
    """Insurer-defined occupation classes (e.g. AIA's Professional/White
    Collar/Light Manual/Heavy Manual). Names vary by insurer - `code` is our
    normalized category used for cross-insurer filtering; `insurer_label` is
    the exact wording as it appears in that insurer's document, kept for
    citation fidelity."""

    __tablename__ = "occupation_category"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=_uuid)
    insurer_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("insurer.id"))
    code: Mapped[str] = mapped_column(String(60))  # normalized, e.g. "professional"
    insurer_label: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class EligibilityRule(Base):
    __tablename__ = "eligibility_rule"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=_uuid)
    policy_version_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("policy_version.id"))
    occupation_category_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("occupation_category.id"), nullable=True
    )
    smoker_status: Mapped[str] = mapped_column(String(20), default="any")
    age_min: Mapped[int] = mapped_column(Integer)
    age_max: Mapped[int] = mapped_column(Integer)
    restriction_type: Mapped[str] = mapped_column(String(20), default="none")  # none|loading|exclusion
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("document.id"), nullable=True
    )
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paragraph_ref: Mapped[str | None] = mapped_column(String(40), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)


class GradedFact(Base):
    """One extracted, citable fact feeding the grading engine - TPD basis,
    trauma condition count, premium structure, waiver of premium, automatic
    benefit count. `category` matches the criterion keys in
    app/services/grading.DEFAULT_WEIGHTS so the repository layer can group
    rows straight into a ProductProfile without a translation table."""

    __tablename__ = "graded_fact"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=_uuid)
    policy_version_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("policy_version.id"))
    category: Mapped[str] = mapped_column(String(40))
    raw_value: Mapped[str] = mapped_column(Text)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("document.id"), nullable=True
    )
    page: Mapped[int] = mapped_column(Integer)
    paragraph_ref: Mapped[str] = mapped_column(String(40))
    confidence: Mapped[float] = mapped_column(Float)
