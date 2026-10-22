"""token_usages.conversation_id nullable (대화 삭제 후에도 사용량 유지)

Revision ID: h8a1b2c3d4e5
Revises: g7a1b2c3d4e5
Create Date: 2026-10-22 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'h8a1b2c3d4e5'
down_revision: Union[str, None] = 'g7a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('token_usages', 'conversation_id', existing_type=sa.String(length=36), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM token_usages WHERE conversation_id IS NULL")
    op.alter_column('token_usages', 'conversation_id', existing_type=sa.String(length=36), nullable=False)
