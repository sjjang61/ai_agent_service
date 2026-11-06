"""browser_profiles (사용자 브라우저 로그인 상태)

Revision ID: m3a1b2c3d4e5
Revises: l2a1b2c3d4e5
Create Date: 2026-11-06 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'm3a1b2c3d4e5'
down_revision: Union[str, None] = 'l2a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'browser_profiles',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, unique=True, index=True),
        sa.Column('state_enc', sa.Text().with_variant(sa.Text(length=4294967295), 'mysql'), nullable=False),
        sa.Column('domains', sa.JSON(), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('browser_profiles')
