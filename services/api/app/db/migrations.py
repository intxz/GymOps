import logging
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


_MIGRATIONS = [
    # (table, column, type, default)
    ("users", "is_admin", "BOOLEAN", "0"),
    ("users", "is_authorized", "BOOLEAN", "0"),
]


def run_sqlite_migrations(engine: Engine) -> None:
    """Add missing columns to existing SQLite tables."""
    with engine.connect() as conn:
        for table, column, col_type, default in _MIGRATIONS:
            # Check if column exists
            result = conn.execute(
                text(f"PRAGMA table_info({table})")
            )
            columns = [row[1] for row in result]
            if column not in columns:
                logger.info("Migration: adding column %s to %s", column, table)
                conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type} NOT NULL DEFAULT {default}")
                )
                conn.commit()
            else:
                logger.debug("Column %s already exists in %s", column, table)
