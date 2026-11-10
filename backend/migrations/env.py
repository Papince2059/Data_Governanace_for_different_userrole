"""
Alembic async migration environment.

Reads DATABASE_URL from the environment (falls back to alembic.ini if not set)
and runs migrations against an async PostgreSQL engine via asyncpg.

Usage:
    alembic upgrade head
    alembic downgrade -1
    alembic revision --autogenerate -m "description"
"""
from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ---------------------------------------------------------------------------
# Make sure the backend/src package is importable from within the migrations/
# directory regardless of how alembic is invoked.
# ---------------------------------------------------------------------------
_backend_root = Path(__file__).resolve().parents[1]  # …/backend
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

# Import all models so that Base.metadata is fully populated before
# autogenerate inspects it.
import src.infrastructure.database.models  # noqa: F401 – side-effect import
from src.infrastructure.database.connection import Base

# ---------------------------------------------------------------------------
# Alembic Config object – gives access to alembic.ini values
# ---------------------------------------------------------------------------
config = context.config

# Honour the [loggers] section from alembic.ini when running from CLI
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url with the DATABASE_URL env var so we never commit
# credentials to source control.
_db_url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
if not _db_url:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set and sqlalchemy.url "
        "is empty in alembic.ini."
    )
config.set_main_option("sqlalchemy.url", _db_url)

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline migrations (generate SQL scripts without a live DB connection)
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Emits SQL to stdout instead of connecting to the database.  Useful for
    generating migration scripts to review or apply manually.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online migrations (connect to a live DB)
# ---------------------------------------------------------------------------


def do_run_migrations(connection: Connection) -> None:
    """Configure the migration context and run pending migrations."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        # Include schemas so that schema-qualified tables are detected
        include_schemas=False,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Create an async engine and run migrations inside a sync connection wrapper.

    asyncpg (the async driver) cannot be used directly with Alembic's
    synchronous migration runner; we therefore call ``run_sync`` to bridge
    the gap.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online (connected) migrations."""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
