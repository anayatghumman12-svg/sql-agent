"""Read-only PostgreSQL access: schema description and query execution."""
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator, Optional

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import connection as PgConnection, cursor as PgCursor

from app import settings

logger = logging.getLogger(__name__)

_COLUMNS_QUERY = """
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = %s
ORDER BY table_name, ordinal_position
"""

# pg_catalog instead of information_schema on purpose: for a role that only
# has SELECT, information_schema hides constraints, so the agent would never
# see the foreign keys.
_KEYS_QUERY = """
SELECT conrelid::regclass::text, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE contype IN ('p', 'f') AND connamespace = %s::regnamespace
ORDER BY 1, 2
"""


@dataclass
class QueryResult:
    """Rows returned by a query, capped at settings.SQL_ROW_LIMIT."""

    columns: list[str]
    rows: list[tuple[Any, ...]]
    truncated: bool


@contextmanager
def _connect() -> Iterator[PgConnection]:
    """Open a short-lived, read-only connection as the agent_ro role.

    Yields:
        A psycopg2 connection that is closed on exit.
    """
    conn = psycopg2.connect(
        settings.DATABASE_URL,
        connect_timeout=settings.DB_CONNECT_TIMEOUT_SECONDS,
        # Server-side kill switch for runaway queries.
        options=f"-c statement_timeout={settings.SQL_TIMEOUT_MS}",
    )
    try:
        # Belt and braces: the role can only SELECT, and the session is
        # read-only as well. The database enforces safety, not Python keyword
        # filters, which are easy to bypass.
        conn.set_session(readonly=True)
        yield conn
    finally:
        conn.close()


def _distinct_values(
    cur: PgCursor, table: str, column: str
) -> Optional[list[str]]:
    """List a column's distinct values if there are only a few of them.

    Args:
        cur: An open cursor.
        table: Table name (quoted safely as an identifier).
        column: Column name (quoted safely as an identifier).

    Returns:
        The sorted distinct non-null values, or None if the column has more
        than settings.SCHEMA_MAX_DISTINCT_VALUES of them (e.g. names, emails).
    """
    cur.execute(
        sql.SQL(
            "SELECT DISTINCT {col} FROM {tbl} WHERE {col} IS NOT NULL "
            "ORDER BY 1 LIMIT %s"
        ).format(col=sql.Identifier(column), tbl=sql.Identifier(table)),
        (settings.SCHEMA_MAX_DISTINCT_VALUES + 1,),
    )
    values = [row[0] for row in cur.fetchall()]
    if len(values) > settings.SCHEMA_MAX_DISTINCT_VALUES:
        return None
    return values


def describe_schema() -> str:
    """Build a text description of the schema for the model.

    Includes columns, types, nullability, primary/foreign keys, and the
    actual values of low-cardinality text columns.

    Returns:
        A multi-line schema description.

    Raises:
        psycopg2.Error: If the database cannot be reached or queried.
    """
    lines_by_table: dict[str, list[str]] = {}
    keys_by_table: dict[str, list[str]] = {}

    with _connect() as conn, conn.cursor() as cur:
        cur.execute(_COLUMNS_QUERY, (settings.SCHEMA_NAME,))
        columns = cur.fetchall()
        cur.execute(_KEYS_QUERY, (settings.SCHEMA_NAME,))
        keys = cur.fetchall()

        for table, column, data_type, nullable in columns:
            line = f"  - {column} {data_type} "
            line += "NULLABLE" if nullable == "YES" else "NOT NULL"
            if data_type in settings.SCHEMA_PROFILED_TYPES:
                values = _distinct_values(cur, table, column)
                if values is not None:
                    line += f"; distinct values: {values}"
            lines_by_table.setdefault(table, []).append(line)

    for table, definition in keys:
        keys_by_table.setdefault(table, []).append(f"  - {definition}")

    parts: list[str] = []
    for table, column_lines in lines_by_table.items():
        parts.append(f"Table {table}")
        parts.extend(column_lines)
        if table in keys_by_table:
            parts.append("  Keys:")
            parts.extend(keys_by_table[table])
        parts.append("")
    return "\n".join(parts)


def execute_query(query: str) -> QueryResult:
    """Run one query read-only and return at most SQL_ROW_LIMIT rows.

    Args:
        query: The SQL text produced by the model.

    Returns:
        A QueryResult. `truncated` is True if more rows existed than the limit.

    Raises:
        psycopg2.Error: On SQL errors, permission errors or timeouts.
        ValueError: If the statement returned no result set.
    """
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(query)
        if cur.description is None:
            raise ValueError("The statement did not return a result set")
        columns = [col.name for col in cur.description]
        # Fetch one extra row so we can tell whether the result was cut off.
        fetched = cur.fetchmany(settings.SQL_ROW_LIMIT + 1)

    truncated = len(fetched) > settings.SQL_ROW_LIMIT
    return QueryResult(columns, fetched[: settings.SQL_ROW_LIMIT], truncated)