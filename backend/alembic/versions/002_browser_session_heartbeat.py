"""browser session heartbeat / STALE fields

Revision ID: 002
Revises: 001
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if "browser_sessions" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("browser_sessions")}
    cols = [
        ("worker_id", sa.String(128)),
        ("browser_state", sa.String(64)),
        ("context_state", sa.String(64)),
        ("last_heartbeat", sa.DateTime(timezone=True)),
        ("last_activity", sa.DateTime(timezone=True)),
    ]
    for name, typ in cols:
        if name not in existing:
            op.add_column("browser_sessions", sa.Column(name, typ, nullable=True))


def downgrade() -> None:
    for name in ("last_activity", "last_heartbeat", "context_state", "browser_state", "worker_id"):
        try:
            op.drop_column("browser_sessions", name)
        except Exception:
            pass
