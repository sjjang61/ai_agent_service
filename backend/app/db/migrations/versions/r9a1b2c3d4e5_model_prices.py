"""model_prices, app_settings (가격 정책 URL·갱신된 모델 단가)

Revision ID: r9a1b2c3d4e5
Revises: q8a1b2c3d4e5
Create Date: 2026-11-06 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'r9a1b2c3d4e5'
down_revision: Union[str, None] = 'q8a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'model_prices',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('model', sa.String(150), nullable=False, unique=True, index=True),
        sa.Column('input_price', sa.Float(), nullable=False),
        sa.Column('cached_input_price', sa.Float(), nullable=True),
        sa.Column('output_price', sa.Float(), nullable=False),
        sa.Column('source_url', sa.String(1000), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_table(
        'app_settings',
        sa.Column('key', sa.String(100), primary_key=True),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('app_settings')
    op.drop_table('model_prices')
