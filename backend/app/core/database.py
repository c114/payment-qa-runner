"""SQLAlchemy engine and session factory."""
from __future__ import annotations

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    settings = get_settings()
    url = settings.database_url
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = 30
    engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


engine = _make_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema() -> None:
    """Add missing columns for create_all-compatible upgrades (SQLite/Postgres)."""
    settings = get_settings()
    cols = {
        "browser_sessions": [
            ("worker_id", "VARCHAR(128)"),
            ("browser_state", "VARCHAR(64)"),
            ("context_state", "VARCHAR(64)"),
            ("last_heartbeat", "TIMESTAMP"),
            ("last_activity", "TIMESTAMP"),
        ],
    }
    with engine.begin() as conn:
        for table, additions in cols.items():
            existing = set()
            if settings.is_sqlite:
                rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
                existing = {r[1] for r in rows}
            else:
                rows = conn.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name=:t"
                ), {"t": table}).fetchall()
                existing = {r[0] for r in rows}
            if not existing:
                continue
            for name, typ in additions:
                if name in existing:
                    continue
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {typ}"))
