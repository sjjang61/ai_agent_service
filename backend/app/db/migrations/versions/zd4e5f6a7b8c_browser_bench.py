"""browser_bench_results (브라우저 자동화 측정 결과)

Revision ID: zd4e5f6a7b8c
Revises: zc3d4e5f6a7b
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "zd4e5f6a7b8c"
down_revision: Union[str, None] = "zc3d4e5f6a7b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "browser_bench_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("site_name", sa.String(100), nullable=False),
        sa.Column("vertical", sa.String(50), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("run_id", sa.String(36), nullable=True),
        sa.Column("run_status", sa.String(20), nullable=False, server_default=""),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("seconds", sa.Integer(), nullable=True),
        sa.Column("steps", sa.Integer(), nullable=True),
        sa.Column("failed_steps", sa.Integer(), nullable=True),
        sa.Column("loop_blocks", sa.Integer(), nullable=True),
        sa.Column("tokens", sa.Integer(), nullable=True),
        sa.Column("heals", sa.Integer(), nullable=True),
        sa.Column("flow", sa.JSON(), nullable=True),
        sa.Column("issues", sa.JSON(), nullable=True),
        sa.Column("errors", sa.JSON(), nullable=True),
        sa.Column("reasons", sa.JSON(), nullable=True),
        sa.Column("env", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_browser_bench_results_label", "browser_bench_results", ["label"])
    op.create_index("ix_bench_label_site", "browser_bench_results", ["label", "site_name"])


def downgrade() -> None:
    op.drop_index("ix_bench_label_site", table_name="browser_bench_results")
    op.drop_index("ix_browser_bench_results_label", table_name="browser_bench_results")
    op.drop_table("browser_bench_results")
