"""Payment Test Runner 2.0.0 fresh schema.

Revision ID: 001_v2_initial
Revises:
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "001_v2_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_enc", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), server_default="READY"),
        sa.Column("selected", sa.Boolean(), server_default=sa.text("0")),
        sa.Column("session_status", sa.String(32), server_default="NONE"),
        sa.Column("session_path", sa.String(512), nullable=True),
        sa.Column("session_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_result", sa.String(64), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "test_data",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pan_enc", sa.Text(), nullable=False),
        sa.Column("pan_masked", sa.String(32), nullable=False),
        sa.Column("pan_last4", sa.String(4), server_default=""),
        sa.Column("expiry", sa.String(16), nullable=False),
        sa.Column("cvc_enc", sa.Text(), nullable=False),
        sa.Column("brand", sa.String(32), nullable=True),
        sa.Column("selected", sa.Boolean(), server_default=sa.text("0")),
        sa.Column("used_count", sa.Integer(), server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), server_default="UNUSED"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("env_type", sa.String(32), server_default="Sandbox"),
        sa.Column("base_url", sa.String(512), server_default=""),
        sa.Column("login_url", sa.String(512), server_default=""),
        sa.Column("target_url", sa.String(512), server_default=""),
        sa.Column("allow_card_fill", sa.Boolean(), server_default=sa.text("0")),
        sa.Column("task_type", sa.String(32), server_default="smoke"),
        sa.Column("adapter_type", sa.String(64), server_default="standard_sandbox_binding"),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("1")),
        sa.Column("is_builtin", sa.Boolean(), server_default=sa.text("0")),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("last_url_test_status", sa.String(32), nullable=True),
        sa.Column("last_url_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "network_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("protocol", sa.String(16), server_default="direct"),
        sa.Column("host", sa.String(255), nullable=True),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(128), nullable=True),
        sa.Column("password_enc", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("0")),
        sa.Column("last_test_status", sa.String(32), nullable=True),
        sa.Column("last_latency_ms", sa.Float(), nullable=True),
        sa.Column("last_test_error", sa.Text(), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id")),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("status", sa.String(32), server_default="NONE"),
        sa.Column("path", sa.String(512), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id")),
        sa.Column("task_snapshot", sa.JSON(), nullable=True),
        sa.Column("network_id", sa.Integer(), sa.ForeignKey("network_profiles.id"), nullable=True),
        sa.Column("network_snapshot", sa.JSON(), nullable=True),
        sa.Column("account_ids", sa.JSON(), nullable=True),
        sa.Column("test_data_ids", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(32), server_default="QUEUED"),
        sa.Column("progress_done", sa.Integer(), server_default="0"),
        sa.Column("progress_total", sa.Integer(), server_default="0"),
        sa.Column("success_count", sa.Integer(), server_default="0"),
        sa.Column("fail_count", sa.Integer(), server_default="0"),
        sa.Column("error_count", sa.Integer(), server_default="0"),
        sa.Column("cancelled_count", sa.Integer(), server_default="0"),
        sa.Column("current_account", sa.String(255), nullable=True),
        sa.Column("current_step", sa.String(128), nullable=True),
        sa.Column("live_log", sa.JSON(), nullable=True),
        sa.Column("stop_requested", sa.Boolean(), server_default=sa.text("0")),
        sa.Column("mode", sa.String(16), server_default="LIVE"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "run_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("runs.id")),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("account_email", sa.String(255), nullable=True),
        sa.Column("test_data_id", sa.Integer(), sa.ForeignKey("test_data.id"), nullable=True),
        sa.Column("test_data_masked", sa.String(32), nullable=True),
        sa.Column("status", sa.String(16), server_default="WAITING"),
        sa.Column("result_code", sa.String(64), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("final_url", sa.String(1024), nullable=True),
        sa.Column("state", sa.String(64), server_default="QUEUED"),
        sa.Column("steps", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Float(), server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("runs.id")),
        sa.Column("run_item_id", sa.Integer(), sa.ForeignKey("run_items.id"), nullable=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("path", sa.String(1024), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(128), nullable=False, unique=True),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    for t in ("artifacts", "run_items", "runs", "sessions", "network_profiles",
              "tasks", "test_data", "accounts", "admins", "settings"):
        op.drop_table(t)
