"""Auth endpoints: register, login, me.

Design: docs/10-AUTH-AND-ACCOUNTS.md - argon2id password hashing,
short-lived JWT access tokens, named-user accounts.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User
from app.db.session import get_db
from app.api.deps import get_current_user
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, session: Session = Depends(get_db)) -> TokenResponse:
    """Create a named-user account and return an access token.

    Password must be >= 8 characters. Email must be unique.
    New accounts start with subscription_active=False, credit_balance=0.
    """
    if len(body.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters",
        )

    existing = session.query(User).filter(User.email == body.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        name=body.name,
        role="consumer",
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    token = create_access_token(str(user.id), user.email, user.role)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, session: Session = Depends(get_db)) -> TokenResponse:
    """Authenticate with email + password, returns a JWT access token."""
    user = session.query(User).filter(User.email == body.email.lower()).first()
    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(str(user.id), user.email, user.role)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def get_me(user: User = Depends(get_current_user)) -> UserOut:
    """Return the authenticated user's profile."""
    return UserOut(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        subscription_active=user.subscription_active,
        credit_balance=user.credit_balance,
        created_at=user.created_at,
    )
