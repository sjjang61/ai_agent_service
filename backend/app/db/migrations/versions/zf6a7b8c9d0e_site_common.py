"""site_common (웹사이트 분석 전체 공통 지침)

Revision ID: zf6a7b8c9d0e
Revises: ze5f6a7b8c9d
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "zf6a7b8c9d0e"
down_revision: Union[str, None] = "ze5f6a7b8c9d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "site_common",
        sa.Column("key", sa.String(20), primary_key=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source", sa.String(20), nullable=False, server_default="seed"),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("site_common")
