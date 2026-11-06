"""messages (conversation_id, created_at) 인덱스: 큰 JSON 열을 정렬하다 나는 MySQL 1038 방지

Revision ID: n5a1b2c3d4e5
Revises: n4a1b2c3d4e5
Create Date: 2026-11-06 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'n5a1b2c3d4e5'
down_revision: Union[str, None] = 'n4a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_messages_conversation_created', 'messages', ['conversation_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_messages_conversation_created', table_name='messages')
