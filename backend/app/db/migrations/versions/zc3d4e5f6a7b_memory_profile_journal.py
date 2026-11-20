"""user_profiles (USER.md), memory_journals (날짜별 일지)

Revision ID: zc3d4e5f6a7b
Revises: zb2c3d4e5f6a
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "zc3d4e5f6a7b"
down_revision: Union[str, None] = "zb2c3d4e5f6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("merged_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "memory_journals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("day", sa.String(10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "day", name="uq_memory_journal_user_day"),
    )
    op.create_index("ix_memory_journals_user_id", "memory_journals", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_memory_journals_user_id", table_name="memory_journals")
    op.drop_table("memory_journals")
    op.drop_table("user_profiles")
