from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_URL

_is_sqlite = DATABASE_URL.startswith("sqlite")

_connect_args = {"check_same_thread": False} if _is_sqlite else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def _get_columns(conn, table_name: str) -> set[str]:
    """Get column names for a table, works with both SQLite and PostgreSQL."""
    insp = inspect(conn)
    return {col["name"] for col in insp.get_columns(table_name)}


def _add_column_if_missing(conn, table: str, column: str, col_type: str, columns: set[str]) -> None:
    if column not in columns:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        lead_columns = _get_columns(conn, "leads")
        _add_column_if_missing(conn, "leads", "company_id", "INTEGER", lead_columns)
        _add_column_if_missing(conn, "leads", "status", "VARCHAR(40) DEFAULT 'new'", lead_columns)
        _add_column_if_missing(conn, "leads", "assigned_price_eur", "INTEGER", lead_columns)
        _add_column_if_missing(conn, "leads", "rooms", "INTEGER", lead_columns)
        _add_column_if_missing(conn, "leads", "distance_km", "FLOAT", lead_columns)
        _add_column_if_missing(conn, "leads", "express", "BOOLEAN DEFAULT false", lead_columns)
        _add_column_if_missing(conn, "leads", "message", "VARCHAR(5000)", lead_columns)
        _add_column_if_missing(conn, "leads", "photo_name", "VARCHAR(255)", lead_columns)
        _add_column_if_missing(conn, "leads", "accepted_agb", "BOOLEAN DEFAULT false", lead_columns)
        _add_column_if_missing(conn, "leads", "accepted_privacy", "BOOLEAN DEFAULT false", lead_columns)
        conn.execute(text("UPDATE leads SET status = 'new' WHERE status IS NULL OR status = ''"))
        conn.execute(text("UPDATE leads SET express = false WHERE express IS NULL"))
        conn.execute(text("UPDATE leads SET accepted_agb = false WHERE accepted_agb IS NULL"))
        conn.execute(text("UPDATE leads SET accepted_privacy = false WHERE accepted_privacy IS NULL"))

        company_columns = _get_columns(conn, "companies")
        _add_column_if_missing(conn, "companies", "last_assigned_at", "TIMESTAMP", company_columns)
        _add_column_if_missing(conn, "companies", "balance_eur", "FLOAT DEFAULT 0", company_columns)
        _add_column_if_missing(conn, "companies", "api_key", "VARCHAR(120)", company_columns)
        conn.execute(text("UPDATE companies SET balance_eur = 0 WHERE balance_eur IS NULL"))
