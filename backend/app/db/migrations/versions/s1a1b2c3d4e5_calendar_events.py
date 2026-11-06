"""calendar_events (사용자가 직접 추가한 캘린더 일정)

Revision ID: s1a1b2c3d4e5
Revises: r9a1b2c3d4e5
Create Date: 2026-11-07 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 's1a1b2c3d4e5'
down_revision: Union[str, None] = 'r9a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'calendar_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('start_date', sa.String(10), nullable=False, index=True),
        sa.Column('end_date', sa.String(10), nullable=False),
        sa.Column('start_time', sa.String(5), nullable=False, server_default=''),
        sa.Column('end_time', sa.String(5), nullable=False, server_default=''),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('memory_id', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('calendar_events')
