"""API key management: create, list, revoke.

Design: docs/10-AUTH-AND-ACCOUNTS.md 'API keys vs. browser sessions'.
Raw key shown exactly once at creation; only SHA-256 hash stored.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import generate_api_key
from app.db.models import ApiKey, User
from app.db.session import get_db
from app.schemas.auth import ApiKeyCreateRequest, ApiKeyCreated, ApiKeyOut

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_api_key(
    body: ApiKeyCreateRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ApiKeyCreated:
    """Generate a new long-lived API key. The raw key is returned exactly
    once and can never be retrieved again - store it securely."""
    raw_key, key_hash, key_prefix = generate_api_key()

    api_key = ApiKey(
        user_id=user.id,
        label=body.label,
        key_hash=key_hash,
        key_prefix=key_prefix,
    )
    session.add(api_key)
    session.commit()
    session.refresh(api_key)

    return ApiKeyCreated(
        id=str(api_key.id),
        label=api_key.label,
        raw_key=raw_key,
        key_prefix=api_key.key_prefix,
        created_at=api_key.created_at,
    )


@router.get("", response_model=list[ApiKeyOut])
def list_api_keys(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[ApiKeyOut]:
    """List all API keys for the current user (raw key never exposed)."""
    keys = (
        session.query(ApiKey)
        .filter(ApiKey.user_id == user.id)
        .order_by(ApiKey.created_at.desc())
        .all()
    )
    return [
        ApiKeyOut(
            id=str(k.id),
            label=k.label,
            key_prefix=k.key_prefix,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
            revoked_at=k.revoked_at,
        )
        for k in keys
    ]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    key_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> None:
    """Revoke an API key immediately. Revoked keys cannot authenticate."""
    api_key = session.get(ApiKey, key_id)
    if not api_key or api_key.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    if api_key.revoked_at:
        return  # already revoked, idempotent
    api_key.revoked_at = datetime.now(timezone.utc)
    session.commit()
