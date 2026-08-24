"""PostgreSQL script execution for Alembic's asyncpg connection.

SQLAlchemy's asyncpg dialect prepares every ``op.execute()`` statement. asyncpg
therefore rejects a whole schema file containing several SQL commands. The raw
schema files also contain PL/pgSQL bodies with semicolons, so ``text.split(';')``
is not safe.

This scanner recognizes the quoting/comment forms used by PostgreSQL DDL and
splits only on semicolons that are outside all of them. Comments are discarded
outside quoted content so a trailing comments-only section never becomes a fake
statement. Each result goes through Alembic's existing transactional connection.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from alembic import op

_DOLLAR_TAG = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$")


def iter_statements(script: str) -> Iterator[str]:
    """Yield top-level PostgreSQL statements without corrupting quoted bodies."""
    buffer: list[str] = []
    index = 0
    length = len(script)
    single_quote = False
    double_quote = False
    line_comment = False
    block_comment_depth = 0
    dollar_tag: str | None = None

    while index < length:
        char = script[index]
        nxt = script[index + 1] if index + 1 < length else ""

        if line_comment:
            index += 1
            if char == "\n":
                line_comment = False
                buffer.append("\n")
            continue

        if block_comment_depth:
            if char == "/" and nxt == "*":
                block_comment_depth += 1
                index += 2
                continue
            if char == "*" and nxt == "/":
                block_comment_depth -= 1
                index += 2
                if not block_comment_depth:
                    buffer.append(" ")
                continue
            index += 1
            continue

        if dollar_tag is not None:
            if script.startswith(dollar_tag, index):
                buffer.append(dollar_tag)
                index += len(dollar_tag)
                dollar_tag = None
            else:
                buffer.append(char)
                index += 1
            continue

        if single_quote:
            buffer.append(char)
            index += 1
            if char == "'":
                if index < length and script[index] == "'":
                    buffer.append("'")
                    index += 1
                else:
                    single_quote = False
            continue

        if double_quote:
            buffer.append(char)
            index += 1
            if char == '"':
                if index < length and script[index] == '"':
                    buffer.append('"')
                    index += 1
                else:
                    double_quote = False
            continue

        if char == "-" and nxt == "-":
            line_comment = True
            index += 2
            continue

        if char == "/" and nxt == "*":
            block_comment_depth = 1
            index += 2
            continue

        if char == "'":
            buffer.append(char)
            single_quote = True
            index += 1
            continue

        if char == '"':
            buffer.append(char)
            double_quote = True
            index += 1
            continue

        if char == "$":
            match = _DOLLAR_TAG.match(script, index)
            if match:
                dollar_tag = match.group(0)
                buffer.append(dollar_tag)
                index = match.end()
                continue

        if char == ";":
            statement = "".join(buffer).strip()
            if statement:
                yield statement
            buffer = []
            index += 1
            continue

        buffer.append(char)
        index += 1

    if single_quote or double_quote or dollar_tag is not None or block_comment_depth:
        raise ValueError("unterminated quoted string, dollar body, or block comment in SQL script")

    statement = "".join(buffer).strip()
    if statement:
        yield statement


def execute_sql_script(script: str) -> int:
    """Execute one raw schema script transactionally and return statement count."""
    count = 0
    for statement in iter_statements(script):
        op.execute(statement)
        count += 1
    if count == 0:
        raise ValueError("SQL script contains no executable statements")
    return count
