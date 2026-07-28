"""SQLAlchemy models for the life-insurance schema extension.

These add three tables on top of the core ERD in docs/02-DATABASE-ERD.md:
occupation_category, eligibility_rule, and graded_fact. They persist exactly
the fields app/domain/models.ProductProfile needs, keyed off policy_version_id
so the repository layer (not yet built - see docs/07-ROADMAP.md weeks 7-8)
can hydrate a ProductProfile from real extracted+verified facts once the
crawler/extractor pipeline is running.

Insurer/Product/PolicyVersion/Document are declared here as thin stand-ins
(id + the columns this module's FKs need) rather than duplicating the full
ORM graph from the eventual `database/` package - importing this module
should not require the whole platform schema to exist yet.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
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


class PolicyVersion(Base):
    __tablename__ = "policy_version"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=_uuid)
    product_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("product.id"))
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="current")


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
    document_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
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
    document_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    page: Mapped[int] = mapped_column(Integer)
    paragraph_ref: Mapped[str] = mapped_column(String(40))
    confidence: Mapped[float] = mapped_column(Float)
