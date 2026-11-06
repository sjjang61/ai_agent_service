"""add token_usages table

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-10-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a1'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('token_usages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('message_id', sa.String(length=36), nullable=True),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('conversation_id', sa.String(length=36), nullable=False),
        sa.Column('llm_provider', sa.String(length=50), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=False, default=0),
        sa.Column('output_tokens', sa.Integer(), nullable=False, default=0),
        sa.Column('agent_name', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_token_usages_message_id'), 'token_usages', ['message_id'], unique=False)
    op.create_index(op.f('ix_token_usages_user_id'), 'token_usages', ['user_id'], unique=False)
    op.create_index(op.f('ix_token_usages_conversation_id'), 'token_usages', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_token_usages_created_at'), 'token_usages', ['created_at'], unique=False)
    op.create_index('ix_token_usages_user_created', 'token_usages', ['user_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_token_usages_user_created', table_name='token_usages')
    op.drop_index(op.f('ix_token_usages_created_at'), table_name='token_usages')
    op.drop_index(op.f('ix_token_usages_conversation_id'), table_name='token_usages')
    op.drop_index(op.f('ix_token_usages_user_id'), table_name='token_usages')
    op.drop_index(op.f('ix_token_usages_message_id'), table_name='token_usages')
    op.drop_table('token_usages')
