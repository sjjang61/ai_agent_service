"""sandboxes.conversation_id (대화방별 sandbox), conversations.space_id (스페이스 대화는 공용 sandbox)

Revision ID: k1a1b2c3d4e5
Revises: j0a1b2c3d4e5
Create Date: 2026-10-22 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'k1a1b2c3d4e5'
down_revision: Union[str, None] = 'j0a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sandboxes', sa.Column('conversation_id', sa.String(length=36), nullable=True))
    op.create_index('ix_sandboxes_conversation_id', 'sandboxes', ['conversation_id'])
    op.add_column('conversations', sa.Column('space_id', sa.String(length=36), nullable=True))
    op.create_index('ix_conversations_space_id', 'conversations', ['space_id'])


def downgrade() -> None:
    op.drop_index('ix_conversations_space_id', table_name='conversations')
    op.drop_column('conversations', 'space_id')
    op.drop_index('ix_sandboxes_conversation_id', table_name='sandboxes')
    op.drop_column('sandboxes', 'conversation_id')
