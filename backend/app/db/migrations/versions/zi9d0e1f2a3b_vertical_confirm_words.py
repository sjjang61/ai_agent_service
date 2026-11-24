"""site_verticals.confirm_words (승인 후 누를 문구)

Revision ID: zi9d0e1f2a3b
Revises: zh8c9d0e1f2a
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "zi9d0e1f2a3b"
down_revision: Union[str, None] = "zh8c9d0e1f2a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("site_verticals", sa.Column("confirm_words", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("site_verticals", "confirm_words")
