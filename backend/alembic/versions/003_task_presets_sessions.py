"""task presets, account sessions, test_run quick-run fields

Revision ID: 003
Revises: 002
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
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

    if "task_presets" not in tables:
        op.create_table(
            "task_presets",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("key", sa.String(64), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("name_zh", sa.String(255), server_default=""),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("description_zh", sa.Text(), nullable=True),
            sa.Column("task_type", sa.String(32), server_default="smoke"),
            sa.Column("start_url", sa.String(512), server_default=""),
            sa.Column("environment_id", sa.Integer(), sa.ForeignKey("environments.id"), nullable=True),
            sa.Column("env_scope", sa.String(32), server_default="production"),
            sa.Column("allow_card_fill", sa.Boolean(), server_default=sa.text("0")),
            sa.Column("open_add_card_modal", sa.Boolean(), server_default=sa.text("1")),
            sa.Column("allowed_domains", sa.JSON(), nullable=True),
            sa.Column("config", sa.JSON(), nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("1")),
            sa.Column("sort_order", sa.Integer(), server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True)),
            sa.Column("updated_at", sa.DateTime(timezone=True)),
        )
        op.create_index("ix_task_presets_key", "task_presets", ["key"], unique=True)

    _add_col("qa_accounts", "session_status", sa.Column("session_status", sa.String(32), server_default="NONE"))
    _add_col("qa_accounts", "session_path", sa.Column("session_path", sa.String(512), nullable=True))
    _add_col("qa_accounts", "session_updated_at", sa.Column("session_updated_at", sa.DateTime(timezone=True), nullable=True))

    _add_col("test_runs", "task_preset_id", sa.Column("task_preset_id", sa.Integer(), sa.ForeignKey("task_presets.id"), nullable=True))
    _add_col("test_runs", "account_ids", sa.Column("account_ids", sa.JSON(), nullable=True))
    _add_col("test_runs", "current_account", sa.Column("current_account", sa.String(255), nullable=True))
    _add_col("test_runs", "current_step", sa.Column("current_step", sa.String(128), nullable=True))
    _add_col("test_runs", "run_mode", sa.Column("run_mode", sa.String(32), server_default="workflow"))
    _add_col("test_runs", "is_mock", sa.Column("is_mock", sa.Boolean(), server_default=sa.text("0")))
    _add_col("test_runs", "error_code", sa.Column("error_code", sa.String(64), nullable=True))


def downgrade() -> None:
    for name in ("error_code", "is_mock", "run_mode", "current_step", "current_account", "account_ids", "task_preset_id"):
        try:
            op.drop_column("test_runs", name)
        except Exception:
            pass
    for name in ("session_updated_at", "session_path", "session_status"):
        try:
            op.drop_column("qa_accounts", name)
        except Exception:
            pass
    try:
        op.drop_index("ix_task_presets_key", table_name="task_presets")
        op.drop_table("task_presets")
    except Exception:
        pass
