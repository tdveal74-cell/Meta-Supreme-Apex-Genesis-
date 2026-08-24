"""Unit coverage for the Alembic PostgreSQL script splitter."""

import pathlib

import pytest

from database.migrations.sql_script import iter_statements


def test_splitter_preserves_dollar_quoted_bodies_and_string_semicolons():
    script = """
    -- leading comment should not become SQL
    CREATE TABLE demo (value TEXT);

    CREATE OR REPLACE FUNCTION demo_trigger()
    RETURNS TRIGGER AS $body$
    BEGIN
        NEW.value = 'inside;string';
        RETURN NEW;
    END;
    $body$ LANGUAGE plpgsql;

    INSERT INTO demo(value) VALUES ('outside;still-string');
    /* outer comment; /* nested; comment */ still comment */
    SELECT 1;
    -- trailing comment only
    """

    statements = list(iter_statements(script))
    assert len(statements) == 4
    assert statements[0].startswith("CREATE TABLE demo")
    assert "NEW.value = 'inside;string';" in statements[1]
    assert statements[1].endswith("$body$ LANGUAGE plpgsql")
    assert statements[2] == "INSERT INTO demo(value) VALUES ('outside;still-string')"
    assert statements[3] == "SELECT 1"


def test_splitter_preserves_doubled_quotes_and_quoted_identifiers():
    script = """
    INSERT INTO "odd;table"(value) VALUES ('Tee''s;value');
    SELECT "semi;column" FROM "odd;table";
    """
    statements = list(iter_statements(script))
    assert len(statements) == 2
    assert "'Tee''s;value'" in statements[0]
    assert '"semi;column"' in statements[1]


def test_splitter_rejects_unterminated_dollar_body():
    with pytest.raises(ValueError, match="unterminated"):
        list(iter_statements("DO $$ BEGIN RAISE NOTICE 'x'; END;"))


def test_real_baseline_schema_splits_function_body_as_one_statement():
    root = pathlib.Path(__file__).resolve().parent
    script = (root / "database" / "schemas" / "001_initial_schema.sql").read_text(
        encoding="utf-8"
    )
    statements = list(iter_statements(script))
    assert len(statements) > 20
    function_statements = [
        statement
        for statement in statements
        if "FUNCTION update_updated_at_column" in statement
    ]
    assert len(function_statements) == 1
    assert "NEW.updated_at = NOW();" in function_statements[0]
