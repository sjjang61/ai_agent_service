"""skills.skill_type (builtin: sandbox 생성 시 자동 설치 / custom: 필요할 때 설치)

Revision ID: p7a1b2c3d4e5
Revises: o6a1b2c3d4e5
Create Date: 2026-11-06 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'p7a1b2c3d4e5'
down_revision: Union[str, None] = 'o6a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('skills', sa.Column('skill_type', sa.String(length=10), nullable=False, server_default='builtin'))


def downgrade() -> None:
    op.drop_column('skills', 'skill_type')
