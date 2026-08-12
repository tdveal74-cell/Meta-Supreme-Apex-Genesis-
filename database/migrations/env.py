"""
Alembic environment — async (asyncpg) aware.

The URL comes from DATABASE_URL so migrations use the same connection string
as the app; `sqlalchemy.url` in alembic.ini stays empty and secret-free. A
plain `postgresql://` URL is upgraded to `postgresql+asyncpg://` so the same
value works for psql, the app, and Alembic.

`target_metadata` is wired to the app's SQLAlchemy metadata when it can be
imported, which enables `--autogenerate`; migrations still run without it.
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

_MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent
_REPO_ROOT = _MIGRATIONS_DIR.parent.parent
for _path in (str(_REPO_ROOT), str(_REPO_ROOT / "apps" / "api")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

config = context.config

if config.config_file_name is not None and not config.attributes.get("quiet_logging"):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

try:  # enables --autogenerate; not required to run migrations
    from app.db.session import Base
    import app.models  # noqa: F401  — registers every mapper on Base.metadata

    target_metadata = Base.metadata
except Exception:  # pragma: no cover - import environment dependent
    target_metadata = None


def _database_url() -> str:
    url = (
        config.get_main_option("sqlalchemy.url")
        or os.environ.get("DATABASE_URL")
        or "postgresql+asyncpg://postgres:postgres@localhost:5432/meta_supreme"
    )
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting (`alembic upgrade head --sql`)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    section = config.get_section(config.config_ini_section, {}) or {}
    section["sqlalchemy.url"] = _database_url()
    engine = async_engine_from_config(
        section, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    async with engine.connect() as connection:
        await connection.run_sync(_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
