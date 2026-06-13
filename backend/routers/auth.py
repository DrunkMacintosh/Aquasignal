"""Authentication endpoints (public)."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.ratelimit import LOGIN_RATE_LIMIT, REGISTER_RATE_LIMIT, limiter
from core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from models.db import User
from models.schemas import LoginRequest, RegisterRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Obtain a JWT access token",
    description=(
        "Exchanges email + password for a bearer token valid for 24 hours. "
        "Pass it as `Authorization: Bearer <token>` on every protected "
        "endpoint. Rate-limited to deter credential stuffing."
    ),
)
@limiter.limit(LOGIN_RATE_LIMIT)
async def login(
    request: Request,  # required by slowapi to key the client IP
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    # body.email arrives lowercased (NormalizedEmail); comparing on
    # lower(email) keeps logins working for legacy accounts that were created
    # with mixed-case addresses via scripts/create_user.py.
    result = await db.execute(
        select(User).where(func.lower(User.email) == body.email)
    )
    user = result.scalar_one_or_none()
    # One generic message for unknown email AND wrong password -- a split
    # response would let attackers enumerate registered accounts.
    if (
        user is None
        or not user.is_active
        or not verify_password(body.password, user.hashed_password)
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    token, expires_in = create_access_token(user)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renew the bearer token",
    description=(
        "Exchanges a valid (not-yet-expired) bearer token for a fresh 24-hour "
        "one, so an open dashboard session never dies mid-shift. Expired or "
        "revoked tokens get 401 — sign in again."
    ),
)
@limiter.limit(LOGIN_RATE_LIMIT)
async def refresh(
    request: Request,  # required by slowapi to key the client IP
    user: User = Depends(get_current_user),
) -> TokenResponse:
    token, expires_in = create_access_token(user)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a water-authority account",
    description=(
        "Self-service sign-up: email + password (12+ characters) and an "
        "optional full name. New accounts always get the lowest-privilege "
        "'field_officer' role -- admins are promoted out-of-band via "
        "scripts/create_user.py. Returns a bearer token so the new user is "
        "signed in immediately. Rate-limited to deter bulk account creation."
    ),
)
@limiter.limit(REGISTER_RATE_LIMIT)
async def register(
    request: Request,  # required by slowapi to key the client IP
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    # lower(email) comparison also blocks case-variants of legacy mixed-case
    # accounts (body.email is already lowercased by NormalizedEmail).
    existing = (
        await db.execute(select(User).where(func.lower(User.email) == body.email))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    # Role is deliberately NOT accepted from the client: self-registration can
    # only ever produce a field_officer, never an admin.
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        # Two concurrent registrations for the same email: uq_users_email
        # (alembic 001) wins the race; report it the same way as the
        # pre-check. Any OTHER integrity failure is a genuine bug, so
        # re-raise and let it surface as a logged 500 instead of a
        # misleading 409.
        if "uq_users_email" not in str(exc.orig):
            raise
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from None
    await db.refresh(user)
    token, expires_in = create_access_token(user)
    return TokenResponse(access_token=token, expires_in=expires_in)
