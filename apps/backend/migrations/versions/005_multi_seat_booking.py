import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
            ondelete="CASCADE",
        ),
        schema="booking",
    )
    op.alter_column("bookings", "seat_id", nullable=True, schema="booking")
    op.drop_constraint(
        "bookings_show_id_seat_id_fkey", "bookings", schema="booking", type_="foreignkey"
    )
    op.create_foreign_key(
        "bookings_show_id_seat_id_fkey",
        "bookings",
        "seats",
        ["show_id", "seat_id"],
        ["show_id", "seat_id"],
        ondelete="CASCADE",
        source_schema="booking",
        referent_schema="booking",
    )


def downgrade() -> None:
    op.drop_constraint(
        "bookings_show_id_seat_id_fkey", "bookings", schema="booking", type_="foreignkey"
    )
    op.create_foreign_key(
        "bookings_show_id_seat_id_fkey",
        "bookings",
        "seats",
        ["show_id", "seat_id"],
        ["show_id", "seat_id"],
        ondelete="RESTRICT",
        source_schema="booking",
        referent_schema="booking",
    )
    op.alter_column("bookings", "seat_id", nullable=False, schema="booking")
    op.drop_table("booking_seats", schema="booking")
