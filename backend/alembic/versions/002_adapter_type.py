"""Add adapter_type to tasks and final_url to run_items.

Revision ID: 002_adapter_type
Revises: 001_v2_initial
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "002_adapter_type"
down_revision = "001_v2_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    task_cols = {c["name"] for c in insp.get_columns("tasks")}
    if "adapter_type" not in task_cols:
        op.add_column(
            "tasks",
            sa.Column("adapter_type", sa.String(64), server_default="standard_sandbox_binding"),
        )
    item_cols = {c["name"] for c in insp.get_columns("run_items")}
    if "final_url" not in item_cols:
        op.add_column("run_items", sa.Column("final_url", sa.String(1024), nullable=True))


def downgrade() -> None:
    # SQLite may not support DROP COLUMN on older versions; best-effort
    try:
        op.drop_column("run_items", "final_url")
    except Exception:
        pass
    try:
        op.drop_column("tasks", "adapter_type")
    except Exception:
        pass
