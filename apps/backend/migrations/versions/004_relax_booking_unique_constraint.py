import sqlalchemy as sa
from alembic import op
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.drop_index('unique_active_booking_per_user_show', schema='booking')
    op.create_index('unique_pending_booking_per_user_show', 'bookings', ['user_id', 'show_id'], schema='booking', unique=True, postgresql_where=sa.text("status = 'PENDING'"))

def downgrade() -> None:
    op.drop_index('unique_pending_booking_per_user_show', schema='booking')
    op.create_index('unique_active_booking_per_user_show', 'bookings', ['user_id', 'show_id'], schema='booking', unique=True, postgresql_where=sa.text("status IN ('PENDING', 'CONFIRMED')"))
