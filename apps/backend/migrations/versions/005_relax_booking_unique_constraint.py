"""NFR-1: Relax unique booking constraint — allow multiple CONFIRMED bookings per user per show.

Revision ID: 005
Revises: 004
"""
from alembic import op
import sqlalchemy as sa


revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the old constraint that blocked both PENDING and CONFIRMED
    op.drop_index(
        "unique_active_booking_per_user_show",
        schema="booking",
    )
    # Recreate with only PENDING — users can now have multiple CONFIRMED bookings
    op.create_index(
        "unique_pending_booking_per_user_show",
        "bookings",
        ["user_id", "show_id"],
        schema="booking",
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
    )


def downgrade() -> None:
    op.drop_index(
        "unique_pending_booking_per_user_show",
        schema="booking",
    )
    op.create_index(
        "unique_active_booking_per_user_show",
        "bookings",
        ["user_id", "show_id"],
        schema="booking",
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING', 'CONFIRMED')"),
    )
