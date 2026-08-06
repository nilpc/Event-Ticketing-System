from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
revision: str = '26cf37c66d8e'
down_revision: Union[str, None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('showtimes', sa.Column('front_price', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'), schema='booking')
    op.add_column('showtimes', sa.Column('middle_price', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'), schema='booking')
    op.add_column('showtimes', sa.Column('back_price', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'), schema='booking')
    op.drop_column('showtimes', 'base_price', schema='booking')
    op.add_column('seats', sa.Column('section', sa.String(length=50), nullable=False, server_default='SEC-1'), schema='booking')

def downgrade() -> None:
    op.drop_column('seats', 'section', schema='booking')
    op.add_column('showtimes', sa.Column('base_price', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'), schema='booking')
    op.drop_column('showtimes', 'back_price', schema='booking')
    op.drop_column('showtimes', 'middle_price', schema='booking')
    op.drop_column('showtimes', 'front_price', schema='booking')
