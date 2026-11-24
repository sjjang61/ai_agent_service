"""skills.subcategory (상세 카테고리)

Revision ID: zj0e1f2a3b4c
Revises: zi9d0e1f2a3b
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "zj0e1f2a3b4c"
down_revision: Union[str, None] = "zi9d0e1f2a3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("skills", sa.Column("subcategory", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("skills", "subcategory")
