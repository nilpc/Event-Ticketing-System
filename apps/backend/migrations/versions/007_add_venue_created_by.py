import sqlalchemy as sa
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "venues",
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        schema="booking",
    )


def downgrade() -> None:
    op.drop_column("venues", "created_by", schema="booking")
