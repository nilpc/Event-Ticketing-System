"""Add event_type enum and STE/STM prefixed IDs.

Revision ID: 002
Create Date: 2026-07-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # --- Create event_type enum ---
    op.execute("CREATE TYPE booking.event_type AS ENUM ('MOVIE', 'EVENT')")

    # --- Create sequences for STE/STM IDs ---
    op.execute("CREATE SEQUENCE IF NOT EXISTS booking.event_serial_seq START 1")
    op.execute("CREATE SEQUENCE IF NOT EXISTS booking.movie_serial_seq START 1")

    # --- Add event_type column (nullable initially) ---
    op.add_column(
        "events",
        sa.Column(
            "event_type",
            sa.Enum("MOVIE", "EVENT", name="event_type", create_type=False),
            nullable=True,
        ),
        schema="booking",
    )

    # --- Convert event_id from UUID to varchar(10) for STE/STM prefix ---

    # Step 1: Drop the FK in showtimes that references events.event_id
    op.drop_constraint("showtimes_event_id_fkey", "showtimes", schema="booking", type_="foreignkey")

    # Step 2: Add temporary varchar column
    op.add_column(
        "events",
        sa.Column("event_id_new", sa.String(10), nullable=True),
        schema="booking",
    )

    # Step 3: Drop PK on old UUID event_id, set NOT NULL, create PK on new column
    op.drop_constraint("events_pkey", "events", schema="booking", type_="primary")
    op.execute("ALTER TABLE booking.events ALTER COLUMN event_id_new SET NOT NULL")
    op.create_primary_key("events_pkey", "events", ["event_id_new"], schema="booking")

    # Step 4: Alter showtimes.event_id from UUID to varchar(10)
    op.alter_column("showtimes", "event_id", schema="booking",
                     type_=sa.String(10), nullable=False)

    # Step 5: Create FK: showtimes.event_id → events.event_id_new
    op.execute(
        "ALTER TABLE booking.showtimes "
        "ADD CONSTRAINT showtimes_event_id_fkey "
        "FOREIGN KEY (event_id) "
        "REFERENCES booking.events (event_id_new) "
        "ON DELETE CASCADE"
    )

    # Step 6: Drop old UUID column, rename new to event_id
    op.drop_column("events", "event_id", schema="booking")
    op.alter_column("events", "event_id_new", schema="booking", new_column_name="event_id")

    # Step 7: Set default event_type for existing rows, then make NOT NULL
    op.execute("UPDATE booking.events SET event_type = 'EVENT' WHERE event_type IS NULL")
    op.alter_column("events", "event_type", schema="booking", nullable=False)


def downgrade() -> None:
    op.drop_constraint("showtimes_event_id_fkey", "showtimes", schema="booking", type_="foreignkey")

    # Add back UUID column
    op.add_column(
        "events",
        sa.Column("event_id_old", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        schema="booking",
    )
    op.execute("UPDATE booking.events SET event_id_old = gen_random_uuid()")

    op.drop_constraint("events_pkey", "events", schema="booking", type_="primary")
    op.execute("ALTER TABLE booking.events ALTER COLUMN event_id_old SET NOT NULL")
    op.create_primary_key("events_pkey", "events", ["event_id_old"], schema="booking")

    op.alter_column("showtimes", "event_id", schema="booking",
                     type_=sa.dialects.postgresql.UUID(as_uuid=True), nullable=False)
    op.create_foreign_key(
        "showtimes_event_id_fkey",
        "showtimes", "events",
        ["event_id"],
        ["event_id_old"],
        schema="booking",
        ondelete="CASCADE",
    )

    op.drop_column("events", "event_id", schema="booking")
    op.alter_column("events", "event_id_old", schema="booking", new_column_name="event_id")

    op.drop_column("events", "event_type", schema="booking")
    op.execute("DROP TYPE IF EXISTS booking.event_type")
    op.execute("DROP SEQUENCE IF EXISTS booking.event_serial_seq")
    op.execute("DROP SEQUENCE IF EXISTS booking.movie_serial_seq")
