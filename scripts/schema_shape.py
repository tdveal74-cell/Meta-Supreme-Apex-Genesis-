"""Dump the shape of a PostgreSQL database so two builds can be diffed.

The repository carries the same schema twice: the Alembic chain under
database/migrations/versions/ (what Railway runs before every deploy) and the
mirrored SQL scripts under database/schemas/ (what conftest applies to the test
database). Nothing proved the two agreed until this script; audit item 3 left
that open, and the divergence it was written to catch was real.

Usage:
    python scripts/schema_shape.py postgresql://user:pass@host/db > shape.txt

The output is deterministic text: one sorted line per column, per constraint
and per index in the public schema, with the alembic_version bookkeeping table
left out because only one of the two builds has it.
"""

from __future__ import annotations

import sys

import psycopg

_SKIP_TABLES = ("alembic_version",)

_COLUMNS = """
SELECT table_name, column_name, data_type,
       COALESCE(character_maximum_length::text, ''),
       is_nullable,
       COALESCE(column_default, '')
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name <> ALL(%s)
ORDER BY table_name, column_name
"""

_CONSTRAINTS = """
SELECT rel.relname, con.conname, pg_get_constraintdef(con.oid)
FROM pg_constraint con
JOIN pg_class rel ON rel.oid = con.conrelid
JOIN pg_namespace ns ON ns.oid = rel.relnamespace
WHERE ns.nspname = 'public' AND rel.relname <> ALL(%s)
ORDER BY rel.relname, con.conname
"""

_INDEXES = """
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public' AND tablename <> ALL(%s)
ORDER BY tablename, indexname
"""


def _emit(cursor, kind: str, sql: str) -> list[str]:
    cursor.execute(sql, (list(_SKIP_TABLES),))
    return [kind + " " + " | ".join(str(value) for value in row) for row in cursor.fetchall()]


def shape(dsn: str) -> str:
    connection = psycopg.connect(dsn)
    try:
        with connection.cursor() as cursor:
            lines = _emit(cursor, "column", _COLUMNS)
            lines += _emit(cursor, "constraint", _CONSTRAINTS)
            lines += _emit(cursor, "index", _INDEXES)
    finally:
        connection.close()
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: schema_shape.py <postgres dsn>", file=sys.stderr)
        return 2
    sys.stdout.write(shape(argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
