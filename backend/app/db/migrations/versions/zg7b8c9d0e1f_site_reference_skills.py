"""site_verticals.reference_skills, site_profiles.reference_skills (웹사이트 분석 참고 스킬)

Revision ID: zg7b8c9d0e1f
Revises: zf6a7b8c9d0e
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "zg7b8c9d0e1f"
down_revision: Union[str, None] = "zf6a7b8c9d0e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("site_verticals", sa.Column("reference_skills", sa.String(300), nullable=True))
    op.add_column("site_profiles", sa.Column("reference_skills", sa.String(300), nullable=True))


def downgrade() -> None:
    op.drop_column("site_profiles", "reference_skills")
    op.drop_column("site_verticals", "reference_skills")
