"""custom agents: agents, agent_versions, conversation/scheduled_task agent links

Revision ID: g7a1b2c3d4e5
Revises: f6a1b2c3d4e5
Create Date: 2026-10-22 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'g7a1b2c3d4e5'
down_revision: Union[str, None] = 'f6a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('agents',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('icon', sa.String(length=8), nullable=False),
        sa.Column('draft_config', sa.JSON(), nullable=False),
        sa.Column('published_version_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'name', name='uq_agents_user_name'),
    )
    op.create_index('ix_agents_user_id', 'agents', ['user_id'])
    op.create_table('agent_versions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('agent_id', sa.String(length=36), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('note', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('agent_id', 'version', name='uq_agent_versions_agent_version'),
    )
    op.create_index('ix_agent_versions_agent_id', 'agent_versions', ['agent_id'])
    op.add_column('conversations', sa.Column('agent_id', sa.String(length=36), nullable=True))
    op.create_index('ix_conversations_agent_id', 'conversations', ['agent_id'])
    op.add_column('conversations', sa.Column('agent_version_id', sa.String(length=36), nullable=True))
    op.add_column('conversations', sa.Column('is_test', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    op.add_column('scheduled_tasks', sa.Column('agent_id', sa.String(length=36), nullable=True))


def downgrade() -> None:
    op.drop_column('scheduled_tasks', 'agent_id')
    op.drop_column('conversations', 'is_test')
    op.drop_column('conversations', 'agent_version_id')
    op.drop_index('ix_conversations_agent_id', table_name='conversations')
    op.drop_column('conversations', 'agent_id')
    op.drop_table('agent_versions')
    op.drop_table('agents')
