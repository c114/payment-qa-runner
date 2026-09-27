"""Normalize NULL test_run columns + TestResult.detail

Revision ID: 004
Revises: 003
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def _add_col(table, name, col):
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if table not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns(table)}
    if name not in existing:
        op.add_column(table, col)


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    tables = set(insp.get_table_names())

    # Ensure quick-run columns exist (idempotent for older DBs)
    if "test_runs" in tables:
        _add_col("test_runs", "account_ids", sa.Column("account_ids", sa.JSON(), nullable=True))
        _add_col("test_runs", "run_mode", sa.Column("run_mode", sa.String(32), server_default="workflow"))
        _add_col("test_runs", "is_mock", sa.Column("is_mock", sa.Boolean(), server_default=sa.text("0")))
        _add_col("test_runs", "proxy_pool_ids", sa.Column("proxy_pool_ids", sa.JSON(), nullable=True))
        _add_col("test_runs", "case_ids", sa.Column("case_ids", sa.JSON(), nullable=True))
        _add_col("test_runs", "live_log", sa.Column("live_log", sa.JSON(), nullable=True))

        # Backfill NULLs — never delete rows
        conn.execute(sa.text("UPDATE test_runs SET account_ids = '[]' WHERE account_ids IS NULL"))
        conn.execute(sa.text("UPDATE test_runs SET proxy_pool_ids = '[]' WHERE proxy_pool_ids IS NULL"))
        conn.execute(sa.text("UPDATE test_runs SET case_ids = '[]' WHERE case_ids IS NULL"))
        conn.execute(sa.text("UPDATE test_runs SET live_log = '[]' WHERE live_log IS NULL"))
        conn.execute(sa.text("UPDATE test_runs SET run_mode = 'workflow' WHERE run_mode IS NULL OR run_mode = ''"))
        # SQLite boolean 0 / Postgres false
        try:
            conn.execute(sa.text("UPDATE test_runs SET is_mock = 0 WHERE is_mock IS NULL"))
        except Exception:
            conn.execute(sa.text("UPDATE test_runs SET is_mock = false WHERE is_mock IS NULL"))

    if "test_results" in tables:
        _add_col("test_results", "detail", sa.Column("detail", sa.JSON(), nullable=True))
        # Normalize NULL list cols if any
        try:
            conn.execute(sa.text("UPDATE test_results SET steps = '[]' WHERE steps IS NULL"))
            conn.execute(sa.text("UPDATE test_results SET screenshot_paths = '[]' WHERE screenshot_paths IS NULL"))
        except Exception:
            pass


def downgrade() -> None:
    try:
        op.drop_column("test_results", "detail")
    except Exception:
        pass
