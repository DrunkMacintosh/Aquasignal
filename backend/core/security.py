"""Password hashing, JWT issue/verify, and auth dependencies.

JWT enforcement is implemented as a router-level dependency rather than raw
ASGI middleware: dependencies show up per-route in the OpenAPI schema (the
docs UI gets a working Authorize button), public routes are opt-out by simply
not declaring the dependency, and the guard is unit-testable in isolation.
"""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.database import get_db
from models.db import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except ValueError:
        # bcrypt 4.x rejects passwords > 72 bytes with ValueError; treat as a
        # failed match (401) rather than letting it surface as a 500.
        return False


def create_access_token(user: User) -> tuple[str, int]:
    """Issue a signed JWT for ``user``. Returns ``(token, expires_in_seconds)``."""
    settings = get_settings()
    expires_in = settings.jwt_expiry_hours * 3600
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_in


def _unauthorized() -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """JWT guard applied to every non-public router."""
    if credentials is None:
        raise _unauthorized()
    settings = get_settings()
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = int(claims["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise _unauthorized() from exc
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized()
    return user


async def require_internal_token(
    x_internal_token: str = Header(
        ..., description="Shared secret for service-to-service calls (monthly cron)."
    ),
) -> None:
    """Guard for internal endpoints called by the cron job, not by users."""
    expected = get_settings().internal_api_token
    # constant-time comparison -- a plain == would leak prefix length via timing
    if not secrets.compare_digest(x_internal_token, expected):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Invalid internal token")
