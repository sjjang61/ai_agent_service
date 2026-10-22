"""wiki_entries: summary, source_text (AI 가 정리한 문서와 원문을 함께 보관)

Revision ID: i9a1b2c3d4e5
Revises: h8a1b2c3d4e5
Create Date: 2026-10-22 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'i9a1b2c3d4e5'
down_revision: Union[str, None] = 'h8a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('wiki_entries', sa.Column('summary', sa.String(length=500), nullable=True))
    op.add_column('wiki_entries', sa.Column('source_text', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('wiki_entries', 'source_text')
    op.drop_column('wiki_entries', 'summary')
