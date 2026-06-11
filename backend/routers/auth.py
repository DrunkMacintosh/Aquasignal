"""Authentication endpoints (public)."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.ratelimit import LOGIN_RATE_LIMIT, limiter
from core.security import create_access_token, verify_password
from models.db import User
from models.schemas import LoginRequest, TokenResponse

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
    result = await db.execute(select(User).where(User.email == body.email))
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
