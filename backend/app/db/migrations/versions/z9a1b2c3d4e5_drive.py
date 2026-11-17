"""drive_nodes, drive_usage (Drive: 개인 파일 공간)

Revision ID: z9a1b2c3d4e5
Revises: y8a1b2c3d4e5
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "z9a1b2c3d4e5"
down_revision: Union[str, None] = "y8a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "drive_nodes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("drive_nodes.id"), nullable=True),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("mime", sa.String(127), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("storage_key", sa.String(255), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="upload"),
        sa.Column("source_ref", sa.JSON(), nullable=True),
        sa.Column("trashed_at", sa.DateTime(), nullable=True),
        sa.Column("trash_root_id", sa.String(36), nullable=True),
        sa.Column("trash_key", sa.String(36), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "parent_id", "name", "trash_key", name="uq_drive_nodes_name"),
    )
    op.create_index("ix_drive_nodes_listing", "drive_nodes", ["user_id", "parent_id", "trashed_at"])
    op.create_table(
        "drive_usage",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("used_bytes", sa.BigInteger(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("drive_usage")
    op.drop_index("ix_drive_nodes_listing", table_name="drive_nodes")
    op.drop_table("drive_nodes")
