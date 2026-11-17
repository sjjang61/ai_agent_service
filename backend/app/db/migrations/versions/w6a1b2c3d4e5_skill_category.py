"""skills: category, category_locked

Revision ID: w6a1b2c3d4e5
Revises: v5a1b2c3d4e5
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "w6a1b2c3d4e5"
down_revision: Union[str, None] = "v5a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("skills", sa.Column("category", sa.String(20), nullable=True))
    op.add_column("skills", sa.Column("category_locked", sa.Boolean(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("skills", "category_locked")
    op.drop_column("skills", "category")
