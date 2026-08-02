"""Pydantic schemas for auth, API keys, and reports."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr


# --- Auth ---


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str  # min 8 chars validated in endpoint
    name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    name: str | None
    role: str
    subscription_active: bool
    credit_balance: int
    created_at: datetime

    model_config = {"from_attributes": True}


# --- API Keys ---


class ApiKeyCreateRequest(BaseModel):
    label: str = "default"


class ApiKeyCreated(BaseModel):
    """Returned exactly once at creation - includes the raw key."""

    id: str
    label: str
    raw_key: str
    key_prefix: str
    created_at: datetime


class ApiKeyOut(BaseModel):
    """List view - never exposes the raw key or hash."""

    id: str
    label: str
    key_prefix: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None

    model_config = {"from_attributes": True}


# --- Reports ---


class HeadToHeadRequest(BaseModel):
    """Two insurers to compare head-to-head for a given product type."""

    insurer_a: str
    insurer_b: str
    product_type: str = "life"


class CriterionResult(BaseModel):
    criterion: str
    insurer_a_value: str | None
    insurer_b_value: str | None
    winner: str | None  # "a", "b", or "tie"
    source_page_a: int | None = None
    source_page_b: int | None = None


class HeadToHeadResponse(BaseModel):
    insurer_a: str
    insurer_b: str
    product_type: str
    criteria: list[CriterionResult]
    credits_remaining: int
    generated_at: datetime
