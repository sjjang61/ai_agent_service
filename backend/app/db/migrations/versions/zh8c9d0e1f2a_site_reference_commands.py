"""site_profiles.reference_commands (참고 스킬 사전 실행 명령)

Revision ID: zh8c9d0e1f2a
Revises: zg7b8c9d0e1f
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "zh8c9d0e1f2a"
down_revision: Union[str, None] = "zg7b8c9d0e1f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("site_profiles", sa.Column("reference_commands", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("site_profiles", "reference_commands")
