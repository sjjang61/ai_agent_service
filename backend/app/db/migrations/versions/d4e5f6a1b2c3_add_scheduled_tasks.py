"""add scheduled_tasks and task_runs tables

Revision ID: d4e5f6a1b2c3
Revises: cf4a817a7c8f
Create Date: 2026-10-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd4e5f6a1b2c3'
down_revision: Union[str, None] = 'cf4a817a7c8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('scheduled_tasks',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('prompt', sa.Text(), nullable=False),
    sa.Column('schedule_type', sa.String(length=20), nullable=False),
    sa.Column('schedule_time', sa.String(length=5), nullable=True),
    sa.Column('weekdays', sa.JSON(), nullable=True),
    sa.Column('day_of_month', sa.Integer(), nullable=True),
    sa.Column('interval_hours', sa.Integer(), nullable=True),
    sa.Column('run_at', sa.DateTime(), nullable=True),
    sa.Column('timezone', sa.String(length=64), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('conversation_id', sa.String(length=36), nullable=True),
    sa.Column('new_conversation_each_run', sa.Boolean(), nullable=False),
    sa.Column('allow_mcp', sa.Boolean(), nullable=False),
    sa.Column('allow_browser', sa.Boolean(), nullable=False),
    sa.Column('llm_provider', sa.String(length=50), nullable=True),
    sa.Column('model_name', sa.String(length=100), nullable=True),
    sa.Column('next_run_at', sa.DateTime(), nullable=True),
    sa.Column('last_run_at', sa.DateTime(), nullable=True),
    sa.Column('last_status', sa.String(length=30), nullable=True),
    sa.Column('consecutive_failures', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scheduled_tasks_user_id'), 'scheduled_tasks', ['user_id'], unique=False)
    op.create_index(op.f('ix_scheduled_tasks_next_run_at'), 'scheduled_tasks', ['next_run_at'], unique=False)
    op.create_table('task_runs',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('task_id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('trigger', sa.String(length=20), nullable=False),
    sa.Column('scheduled_for', sa.DateTime(), nullable=True),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('finished_at', sa.DateTime(), nullable=True),
    sa.Column('conversation_id', sa.String(length=36), nullable=True),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('read_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['task_id'], ['scheduled_tasks.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_task_runs_task_id'), 'task_runs', ['task_id'], unique=False)
    op.create_index(op.f('ix_task_runs_user_id'), 'task_runs', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_task_runs_user_id'), table_name='task_runs')
    op.drop_index(op.f('ix_task_runs_task_id'), table_name='task_runs')
    op.drop_table('task_runs')
    op.drop_index(op.f('ix_scheduled_tasks_next_run_at'), table_name='scheduled_tasks')
    op.drop_index(op.f('ix_scheduled_tasks_user_id'), table_name='scheduled_tasks')
    op.drop_table('scheduled_tasks')
