"""published_apps (웹앱 배포)

Revision ID: u4a1b2c3d4e5
Revises: t3a1b2c3d4e5
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'u4a1b2c3d4e5'
down_revision: Union[str, None] = 't3a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'published_apps',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('conversation_id', sa.String(36), nullable=True),
        sa.Column('name', sa.String(60), nullable=False),
        sa.Column('kind', sa.String(10), nullable=False, server_default='static'),
        sa.Column('proxy_port', sa.Integer(), nullable=True, unique=True),
        sa.Column('container_port', sa.Integer(), nullable=False, server_default='5173'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('artifact_size', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(10), nullable=False, server_default='stopped'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('require_token', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('access_token', sa.String(64), nullable=False),
        sa.Column('container_id', sa.String(80), nullable=True),
        sa.Column('last_request_at', sa.DateTime(), nullable=True),
        sa.Column('last_log', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('user_id', 'name', name='uq_published_app_user_name'),
    )


def downgrade() -> None:
    op.drop_table('published_apps')
