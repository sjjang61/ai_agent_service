"""scheduled_tasks.notify_mode/notify_condition/last_result, task_runs.notify (예약 작업의 조건부 알림)

Revision ID: zb2c3d4e5f6a
Revises: za1b2c3d4e5f
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "zb2c3d4e5f6a"
down_revision: Union[str, None] = "za1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None




def upgrade() -> None:
    op.add_column("scheduled_tasks", sa.Column("notify_mode", sa.String(20), nullable=False, server_default="always"))
    op.add_column("scheduled_tasks", sa.Column("notify_condition", sa.Text(), nullable=True))
    op.add_column("scheduled_tasks", sa.Column("last_result", sa.Text(), nullable=True))
    op.add_column("task_runs", sa.Column("notify", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column("task_runs", "notify")
    op.drop_column("scheduled_tasks", "last_result")
    op.drop_column("scheduled_tasks", "notify_condition")
    op.drop_column("scheduled_tasks", "notify_mode")
