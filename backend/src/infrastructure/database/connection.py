"""
Async SQLAlchemy engine, session factory, and declarative base.

Usage (FastAPI):
    app.add_event_handler("startup", init_db)

    @router.get("/items")
    async def list_items(db: AsyncSession = Depends(get_db_session)):
        ...
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.core.config import get_settings
from src.core.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Declarative base – imported by all ORM model modules
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Shared declarative base for all SQLAlchemy ORM models."""


# ---------------------------------------------------------------------------
# Engine & session factory (module-level singletons, created lazily)
# ---------------------------------------------------------------------------

_engine = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine():
    """Return (creating if necessary) the async SQLAlchemy engine."""
    global _engine  # noqa: PLW0603
    if _engine is None:
        settings = get_settings()
        extra_kwargs = {}
        if "sqlite" not in settings.DATABASE_URL:
            extra_kwargs["pool_size"] = settings.DATABASE_POOL_SIZE
            extra_kwargs["max_overflow"] = settings.DATABASE_MAX_OVERFLOW

        _engine = create_async_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            echo=settings.is_development,
            future=True,
            **extra_kwargs,
        )
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return (creating if necessary) the async session factory."""
    global _async_session_factory  # noqa: PLW0603
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=_get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _async_session_factory


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a transactional :class:`AsyncSession`.

    The session is committed on success and rolled back on any exception,
    then closed in the ``finally`` block.

    Example::

        @router.post("/documents")
        async def create_doc(db: AsyncSession = Depends(get_db_session)):
            ...
    """
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Startup helper
# ---------------------------------------------------------------------------


async def init_db() -> None:
    """
    Validate the database connection at application startup.

    This does **not** run migrations – use Alembic for schema management.
    It simply confirms that the engine can connect so we fail fast rather
    than at the first real query.
    """
    engine = _get_engine()
    try:
        async with engine.connect() as conn:
            await conn.exec_driver_sql("SELECT 1")
        log.info("database_connection_ok", url=get_settings().DATABASE_URL.split("@")[-1])
    except Exception as exc:
        log.error("database_connection_failed", error=str(exc))
        raise


async def close_db() -> None:
    """Dispose the engine connection pool (call on application shutdown)."""
    global _engine  # noqa: PLW0603
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        log.info("database_connection_pool_closed")
