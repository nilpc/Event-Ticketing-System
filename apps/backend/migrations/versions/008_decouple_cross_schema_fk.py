"""Decouple cross-schema FK from booking.bookings to identity.users and add PostgreSQL LISTEN/NOTIFY trigger for outbox relay.

Revision ID: 008
Revises: 007
"""
import sqlalchemy as sa
from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop cross-schema FK constraint to allow microservice schema isolation
    try:
        op.drop_constraint("bookings_user_id_fkey", "bookings", schema="booking", type_="foreignkey")
    except Exception:
        pass

    # 2. Add PostgreSQL LISTEN/NOTIFY trigger on booking.outbox_events for instant event-driven relaying
    op.execute(
        """
        CREATE OR REPLACE FUNCTION booking.notify_outbox_inserted()
        RETURNS trigger AS $$
        BEGIN
            PERFORM pg_notify('outbox_inserted', NEW.event_id::text);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_outbox_inserted ON booking.outbox_events;")
    op.execute(
        """
        CREATE TRIGGER trg_outbox_inserted
        AFTER INSERT ON booking.outbox_events
        FOR EACH ROW EXECUTE FUNCTION booking.notify_outbox_inserted();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_outbox_inserted ON booking.outbox_events;")
    op.execute("DROP FUNCTION IF EXISTS booking.notify_outbox_inserted();")
    op.create_foreign_key(
        "bookings_user_id_fkey",
        "bookings",
        "users",
        ["user_id"],
        ["user_id"],
        source_schema="booking",
        referent_schema="identity",
        ondelete="RESTRICT",
    )
