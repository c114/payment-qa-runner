"""SQLAlchemy engine and session factory — 2.0 fresh schema."""
from __future__ import annotations

from sqlalchemy import create_engine, event
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
    """Additive SQLite column patches for 2.0.x (safe on fresh + existing DBs)."""
    from sqlalchemy import text
    settings = get_settings()
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.begin() as conn:
        cols_tasks = {r[1] for r in conn.execute(text("PRAGMA table_info(tasks)")).fetchall()}
        if "adapter_type" not in cols_tasks:
            conn.execute(text(
                "ALTER TABLE tasks ADD COLUMN adapter_type VARCHAR(64) DEFAULT 'standard_sandbox_binding'"
            ))
        cols_items = {r[1] for r in conn.execute(text("PRAGMA table_info(run_items)")).fetchall()}
        if "final_url" not in cols_items:
            conn.execute(text("ALTER TABLE run_items ADD COLUMN final_url VARCHAR(1024)"))
