"""Apply database/grants/devon_api.sql as the database owner.

The compose stack's migrate service runs this after ``alembic upgrade head``,
so every table a migration creates is granted to the runtime role in the same
step that created it. Reads DATABASE_URL (the owner's), rewrites the
SQLAlchemy scheme for asyncpg, binds the two psql style variables the file
uses, and executes it statement by statement through the same splitter the
migrations use. Fails loudly when the role does not exist: a stack that never
ran the initdb script has no role to grant, and that is worth stopping on.
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from database.migrations.sql_script import iter_statements  # noqa: E402

GRANTS = _HERE / "devon_api.sql"
ROLE = "devon_api"


def _dsn() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("DATABASE_URL is not set; the owner's URL is required to grant")
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def main() -> int:
    import asyncpg

    conn = await asyncpg.connect(dsn=_dsn())
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", ROLE)
        if not exists:
            raise SystemExit(
                f"role {ROLE} does not exist on this database; the initdb script "
                "infrastructure/docker/initdb/020-api-role.sh creates it on first "
                "start, or run initdb/sql/api-role.sql by hand"
            )
        owner = await conn.fetchval("SELECT current_user")
        script = GRANTS.read_text(encoding="utf-8").replace(':"owner_role"', f'"{owner}"')
        count = 0
        async with conn.transaction():
            for statement in iter_statements(script):
                await conn.execute(statement)
                count += 1
        print(f"applied {count} grant statement(s) for {ROLE} as {owner}")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
