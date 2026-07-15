"""Ensure STE/STM ID sequences exist.

Revision ID: 003
Create Date: 2026-07-15

Sequences may be lost after schema recreation. This migration
idempotently ensures they exist.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS booking.event_serial_seq START 1")
    op.execute("CREATE SEQUENCE IF NOT EXISTS booking.movie_serial_seq START 1")


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS booking.event_serial_seq")
    op.execute("DROP SEQUENCE IF EXISTS booking.movie_serial_seq")
