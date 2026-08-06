from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    try:
        op.drop_constraint(
            "bookings_user_id_fkey", "bookings", schema="booking", type_="foreignkey"
        )
    except Exception:
        pass
    op.execute(
        "\n        CREATE OR REPLACE FUNCTION booking.notify_outbox_inserted()\n        RETURNS trigger AS $$\n        BEGIN\n            PERFORM pg_notify('outbox_inserted', NEW.event_id::text);\n            RETURN NEW;\n        END;\n        $$ LANGUAGE plpgsql;\n        "
    )
    op.execute("DROP TRIGGER IF EXISTS trg_outbox_inserted ON booking.outbox_events;")
    op.execute(
        "\n        CREATE TRIGGER trg_outbox_inserted\n        AFTER INSERT ON booking.outbox_events\n        FOR EACH ROW EXECUTE FUNCTION booking.notify_outbox_inserted();\n        "
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
