"""add memory_type, occurred_at, detail to memories

Revision ID: e5f6a1b2c3d4
Revises: d4e5f6a1b2c3
Create Date: 2026-10-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e5f6a1b2c3d4'
down_revision: Union[str, None] = 'd4e5f6a1b2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('memories', sa.Column('memory_type', sa.String(length=20), nullable=False, server_default='semantic'))
    op.create_index('ix_memories_memory_type', 'memories', ['memory_type'])
    op.add_column('memories', sa.Column('occurred_at', sa.DateTime(), nullable=True))
    op.add_column('memories', sa.Column('detail', sa.JSON(), nullable=True))
    # 기존 지침(instruction)은 절차 기억으로 옮긴다
    op.execute("UPDATE memories SET memory_type = 'procedural' WHERE category = 'instruction'")


def downgrade() -> None:
    op.drop_column('memories', 'detail')
    op.drop_column('memories', 'occurred_at')
    op.drop_index('ix_memories_memory_type', table_name='memories')
    op.drop_column('memories', 'memory_type')
