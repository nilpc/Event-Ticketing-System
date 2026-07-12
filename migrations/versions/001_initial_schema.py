"""FR-1, FR-5, FR-8, FR-9, FR-10, NFR-1: Initial schema — identity + booking.

Revision ID: 001
Create Date: 2026-07-12
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # ================================================================
    # SCHEMAS
    # ================================================================
    op.execute("CREATE SCHEMA IF NOT EXISTS identity")
    op.execute("CREATE SCHEMA IF NOT EXISTS booking")
    op.execute("CREATE SCHEMA IF NOT EXISTS alembic")

    # ================================================================
    # IDENTITY SCHEMA
    # ================================================================

    # --- identity.users ---
    op.create_table(
        "users",
        sa.Column("user_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("google_subject_id", sa.String(255), unique=True, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_attempts", sa.Integer, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        # FR-1: GDPR soft-delete and anonymization
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("anonymized", sa.Boolean, server_default="false"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        schema="identity",
    )

    # --- identity.refresh_tokens ---
    op.create_table(
        "refresh_tokens",
        sa.Column("token_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("identity.users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(255), unique=True, nullable=False),
        sa.Column("rotated_from", UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_revoked", sa.Boolean, server_default="false"),
        schema="identity",
    )

    # ================================================================
    # BOOKING SCHEMA
    # ================================================================

    # --- booking.venues ---
    op.create_table(
        "venues",
        sa.Column("venue_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("capacity", sa.Integer, nullable=False),
        schema="booking",
    )

    # --- booking.events ---
    op.create_table(
        "events",
        sa.Column("event_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        schema="booking",
    )

    # --- booking.showtimes ---
    op.create_table(
        "showtimes",
        sa.Column("show_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "event_id",
            UUID(as_uuid=True),
            sa.ForeignKey("booking.events.event_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "venue_id",
            UUID(as_uuid=True),
            sa.ForeignKey("booking.venues.venue_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("base_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        schema="booking",
    )

    # --- booking.seats ---
    op.create_table(
        "seats",
        sa.Column(
            "show_id",
            UUID(as_uuid=True),
            sa.ForeignKey("booking.showtimes.show_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("seat_id", sa.String(10), primary_key=True),
        sa.Column("tier", sa.String(20), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "AVAILABLE", "PENDING_PAYMENT", "SOLD",
                name="seat_status",
            ),
            nullable=False,
            server_default="AVAILABLE",
        ),
        schema="booking",
    )

    # --- booking.bookings (with cross-schema FK to identity.users) ---
    op.create_table(
        "bookings",
        sa.Column("booking_id", UUID(as_uuid=True), primary_key=True),
        # FR-1: cross-schema foreign key
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("identity.users.user_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("show_id", UUID(as_uuid=True), nullable=False),
        sa.Column("seat_id", sa.String(10), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING", "CONFIRMED", "FAILED", "CANCELLED",
                name="booking_status",
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "idempotency_key", sa.String(255), unique=True, nullable=False
        ),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        # Composite FK to seats
        sa.ForeignKeyConstraint(
            ["show_id", "seat_id"],
            ["booking.seats.show_id", "booking.seats.seat_id"],
            ondelete="RESTRICT",
        ),
        schema="booking",
    )

    # --- booking.payments ---
    op.create_table(
        "payments",
        sa.Column("payment_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "booking_id",
            UUID(as_uuid=True),
            sa.ForeignKey("booking.bookings.booking_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column(
            "provider_payment_id", sa.String(255), unique=True, nullable=True
        ),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        schema="booking",
    )

    # --- booking.booking_events ---
    op.create_table(
        "booking_events",
        sa.Column("event_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "booking_id",
            UUID(as_uuid=True),
            sa.ForeignKey("booking.bookings.booking_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_status",
            sa.Enum(
                "PENDING", "CONFIRMED", "FAILED", "CANCELLED",
                name="booking_status",
            ),
            nullable=True,
        ),
        sa.Column(
            "to_status",
            sa.Enum(
                "PENDING", "CONFIRMED", "FAILED", "CANCELLED",
                name="booking_status",
            ),
            nullable=False,
        ),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("correlation_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "changed_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        schema="booking",
    )

    # --- booking.processed_webhook_events ---
    op.create_table(
        "processed_webhook_events",
        sa.Column("event_id", sa.String(255), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column(
            "processed_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        schema="booking",
    )

    # --- booking.outbox_events ---
    op.create_table(
        "outbox_events",
        sa.Column("event_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("aggregate_type", sa.String(50), nullable=True),
        sa.Column("aggregate_id", UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=True),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        schema="booking",
    )

    # ================================================================
    # INDEXES
    # ================================================================

    # FR-9: Zombie sweeper — fast scan of PENDING bookings by expires_at
    op.create_index(
        "idx_zombie_sweeper",
        "bookings",
        ["status", "expires_at"],
        schema="booking",
        postgresql_where=sa.text("status = 'PENDING'"),
    )

    # NFR-1: One active booking per user per showtime
    op.create_index(
        "unique_active_booking_per_user_show",
        "bookings",
        ["user_id", "show_id"],
        schema="booking",
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING', 'CONFIRMED')"),
    )

    # FR-5: At most one non-terminal payment intent per booking
    op.create_index(
        "unique_active_payment_per_booking",
        "payments",
        ["booking_id"],
        schema="booking",
        unique=True,
        postgresql_where=sa.text("status IN ('initiated', 'requires_action')"),
    )

    # Outbox relay: fast scan of unpublished events
    op.create_index(
        "idx_outbox_unpublished",
        "outbox_events",
        ["created_at"],
        schema="booking",
        postgresql_where=sa.text("published_at IS NULL"),
    )

    # Seat lookup: availability checks by show
    op.create_index(
        "idx_seats_lookup",
        "seats",
        ["show_id", "status"],
        schema="booking",
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_index("idx_seats_lookup", schema="booking")
    op.drop_index("idx_outbox_unpublished", schema="booking")
    op.drop_index("unique_active_payment_per_booking", schema="booking")
    op.drop_index("unique_active_booking_per_user_show", schema="booking")
    op.drop_index("idx_zombie_sweeper", schema="booking")

    op.drop_table("outbox_events", schema="booking")
    op.drop_table("processed_webhook_events", schema="booking")
    op.drop_table("booking_events", schema="booking")
    op.drop_table("payments", schema="booking")
    op.drop_table("bookings", schema="booking")
    op.drop_table("seats", schema="booking")
    op.drop_table("showtimes", schema="booking")
    op.drop_table("events", schema="booking")
    op.drop_table("venues", schema="booking")

    op.drop_table("refresh_tokens", schema="identity")
    op.drop_table("users", schema="identity")

    # Drop enums
    sa.Enum(name="booking_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="seat_status").drop(op.get_bind(), checkfirst=True)

    # Drop schemas
    op.execute("DROP SCHEMA IF EXISTS booking")
    op.execute("DROP SCHEMA IF EXISTS identity")
    op.execute("DROP SCHEMA IF EXISTS alembic")
