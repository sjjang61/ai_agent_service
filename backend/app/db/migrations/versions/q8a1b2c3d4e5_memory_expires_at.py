"""memories.expires_at (유효기간이 있는 메모리)

Revision ID: q8a1b2c3d4e5
Revises: p7a1b2c3d4e5
Create Date: 2026-11-06 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'q8a1b2c3d4e5'
down_revision: Union[str, None] = 'p7a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('memories', sa.Column('expires_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('memories', 'expires_at')
