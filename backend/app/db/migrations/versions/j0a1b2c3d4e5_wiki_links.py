"""wiki_entries.links (문서 간 연결)

Revision ID: j0a1b2c3d4e5
Revises: i9a1b2c3d4e5
Create Date: 2026-10-22 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'j0a1b2c3d4e5'
down_revision: Union[str, None] = 'i9a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('wiki_entries', sa.Column('links', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('wiki_entries', 'links')
