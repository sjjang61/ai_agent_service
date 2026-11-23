"""site_verticals.category, site_profiles.category (웹사이트 분석 카테고리)

Revision ID: ze5f6a7b8c9d
Revises: zd4e5f6a7b8c
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "ze5f6a7b8c9d"
down_revision: Union[str, None] = "zd4e5f6a7b8c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("site_verticals", sa.Column("category", sa.String(30), nullable=True))
    op.add_column("site_profiles", sa.Column("category", sa.String(30), nullable=True))


def downgrade() -> None:
    op.drop_column("site_profiles", "category")
    op.drop_column("site_verticals", "category")
