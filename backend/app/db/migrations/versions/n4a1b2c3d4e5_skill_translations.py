"""skill_translations (스킬 문서 한국어 번역 기록)

Revision ID: n4a1b2c3d4e5
Revises: m3a1b2c3d4e5
Create Date: 2026-11-06 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'n4a1b2c3d4e5'
down_revision: Union[str, None] = 'm3a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'skill_translations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('translated', sa.Text().with_variant(sa.Text(length=4294967295), 'mysql'), nullable=False),
        sa.Column('truncated', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('user_id', 'content_hash', name='uq_skill_translations_user_hash'),
    )


def downgrade() -> None:
    op.drop_table('skill_translations')
