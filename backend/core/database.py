"""Async SQLAlchemy engine and per-request session dependency."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import get_settings

engine = create_async_engine(
    get_settings().database_url,
    pool_pre_ping=True,  # recycle connections dropped by the server
    pool_size=10,
    max_overflow=20,
)

SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request.

    The ``async with`` block guarantees the connection returns to the pool
    even when the endpoint raises; uncommitted work is rolled back.
    """
    async with SessionFactory() as session:
        yield session
