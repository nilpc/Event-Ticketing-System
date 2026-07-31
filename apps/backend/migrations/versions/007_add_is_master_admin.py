"""Add is_master_admin to identity.users for superadmin role.

Revision ID: 007
Revises: 006
"""
import sqlalchemy as sa
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_master_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        schema="identity",
    )


def downgrade() -> None:
    op.drop_column("users", "is_master_admin", schema="identity")
