"""user_tool_settings (사용자별 도구 활성화/비활성화)

Revision ID: o6a1b2c3d4e5
Revises: n5a1b2c3d4e5
Create Date: 2026-11-06 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'o6a1b2c3d4e5'
down_revision: Union[str, None] = 'n5a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_tool_settings',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('tool_name', sa.String(100), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('user_id', 'tool_name', name='uq_user_tool_settings_user_tool'),
    )


def downgrade() -> None:
    op.drop_table('user_tool_settings')
