"""Multi-seat booking: create booking.booking_seats junction table.

Revision ID: 006
Revises: 005
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create junction table
    op.create_table(
        "booking_seats",
        sa.Column(
            "booking_id",
            UUID(as_uuid=True),
            sa.ForeignKey("booking.bookings.booking_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("show_id", UUID(as_uuid=True), nullable=False),
        sa.Column("seat_id", sa.String(10), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.PrimaryKeyConstraint("booking_id", "seat_id"),
        sa.ForeignKeyConstraint(
            ["show_id", "seat_id"],
            ["booking.seats.show_id", "booking.seats.seat_id"],
            ondelete="RESTRICT",
        ),
        schema="booking",
    )

    # Make old seat_id column nullable (existing single-seat rows keep it)
    op.alter_column(
        "bookings", "seat_id", nullable=True, schema="booking"
    )


def downgrade() -> None:
    op.alter_column(
        "bookings", "seat_id", nullable=False, schema="booking"
    )
    op.drop_table("booking_seats", schema="booking")
