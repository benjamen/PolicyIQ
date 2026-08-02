"""FastAPI dependencies for authentication and credit gating.

Resolves the current user from either:
1. A Bearer JWT access token (browser/session flow), or
2. An X-API-Key header (programmatic/company API flow).

Credit gating: `require_credit` checks the user has sufficient credits
(or an active subscription) but does NOT deduct - deduction happens in
the endpoint after successful report generation, so failed requests
(e.g. 404 no data) never cost a credit.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import decode_access_token, hash_api_key
from app.db.models import ApiKey, CreditLedger, User
from app.db.session import get_db


def get_current_user(
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None),
    session: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from JWT bearer or API key.

    Priority: X-API-Key header wins if present (company API flow);
    otherwise falls back to Authorization: Bearer <jwt>.
    """
    # --- API key path ---
    if x_api_key:
        key_hash = hash_api_key(x_api_key)
        api_key = (
            session.query(ApiKey)
            .filter(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
            .first()
        )
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked API key",
            )
        user = session.get(User, api_key.user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        # Touch last_used_at
        api_key.last_used_at = datetime.now(timezone.utc)
        session.commit()
        return user

    # --- JWT bearer path ---
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        payload = decode_access_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        user = session.get(User, payload["sub"])
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide a Bearer token or X-API-Key header.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_credit(
    user: User = Depends(get_current_user),
) -> User:
    """Gate that ensures the user CAN generate a comparison (check only).

    - Subscription users: unlimited (flat-rate, not metered).
    - Credit users: must have credit_balance >= 1.
    - Free users with no subscription and no credits: 402 Payment Required.

    Does NOT deduct - the endpoint deducts after successful generation so
    that failed requests (404 no data, validation errors) never cost a credit.
    """
    if user.subscription_active:
        return user

    if user.credit_balance < 1:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient credits. Purchase credits or activate a subscription.",
        )

    return user


def deduct_credit(user: User, session: Session, reference: str | None = None) -> None:
    """Deduct 1 credit from the user and record it in the ledger.

    Call this AFTER successful report generation. Subscription users are
    not metered (no deduction).
    """
    if user.subscription_active:
        return

    user.credit_balance -= 1
    ledger_entry = CreditLedger(
        user_id=user.id,
        delta=-1,
        reason="comparison_generated",
        reference=reference,
    )
    session.add(ledger_entry)
    session.commit()
