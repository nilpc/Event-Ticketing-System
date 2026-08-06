import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema="identity",
    )
    op.add_column(
        "users",
        sa.Column("is_master_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        schema="identity",
    )


def downgrade() -> None:
    op.drop_column("users", "is_master_admin", schema="identity")
    op.drop_column("users", "is_admin", schema="identity")
