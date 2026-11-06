"""published_apps 가시성·스토어 컬럼, app_reports

Revision ID: v5a1b2c3d4e5
Revises: u4a1b2c3d4e5
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'v5a1b2c3d4e5'
down_revision: Union[str, None] = 'u4a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('published_apps', sa.Column('visibility', sa.String(10), nullable=False, server_default='private'))
    op.add_column('published_apps', sa.Column('slug', sa.String(70), nullable=True))
    op.add_column('published_apps', sa.Column('session_epoch', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('published_apps', sa.Column('moderation_status', sa.String(12), nullable=False, server_default=''))
    op.add_column('published_apps', sa.Column('moderation_note', sa.Text(), nullable=True))
    op.add_column('published_apps', sa.Column('title', sa.String(100), nullable=True))
    op.add_column('published_apps', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('published_apps', sa.Column('category', sa.String(30), nullable=True))
    op.add_column('published_apps', sa.Column('tags', sa.JSON(), nullable=True))
    op.add_column('published_apps', sa.Column('listed_at', sa.DateTime(), nullable=True))
    op.add_column('published_apps', sa.Column('launch_count', sa.Integer(), nullable=False, server_default='0'))
    op.create_index('ux_published_apps_slug', 'published_apps', ['slug'], unique=True)
    op.create_index('ix_published_apps_visibility', 'published_apps', ['visibility'])
    op.create_table(
        'app_reports',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('app_id', sa.String(36), nullable=False, index=True),
        sa.Column('reporter_id', sa.String(36), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('app_id', 'reporter_id', name='uq_app_report'),
    )


def downgrade() -> None:
    op.drop_table('app_reports')
    op.drop_index('ix_published_apps_visibility', 'published_apps')
    op.drop_index('ux_published_apps_slug', 'published_apps')
    for c in ('launch_count', 'listed_at', 'tags', 'category', 'description', 'title', 'moderation_note', 'moderation_status', 'session_epoch', 'slug', 'visibility'):
        op.drop_column('published_apps', c)
