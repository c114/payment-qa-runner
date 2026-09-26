"""initial schema via create_all compatibility

Revision ID: 001
Revises:
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tables created by Base.metadata.create_all on startup; this revision marks baseline.
    pass


def downgrade() -> None:
    pass
