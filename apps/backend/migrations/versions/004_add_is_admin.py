"""Add is_admin column to identity.users

Revision ID: 004
Revises: 003
Create Date: 2025-07-17
"""

import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema="identity",
    )


def downgrade() -> None:
    op.drop_column("users", "is_admin", schema="identity")
