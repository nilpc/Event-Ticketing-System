import sqlalchemy as sa
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        schema="booking",
    )


def downgrade() -> None:
    op.drop_column("events", "created_by", schema="booking")
