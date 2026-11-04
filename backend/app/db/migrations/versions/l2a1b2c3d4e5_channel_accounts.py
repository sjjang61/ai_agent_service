"""channel_accounts (메신저 연동), conversations.channel

Revision ID: l2a1b2c3d4e5
Revises: k1a1b2c3d4e5
Create Date: 2026-10-29 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'l2a1b2c3d4e5'
down_revision: Union[str, None] = 'k1a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('conversations', sa.Column('channel', sa.String(length=20), nullable=True))
    op.create_table(
        'channel_accounts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('channel', sa.String(20), nullable=False),
        sa.Column('token_enc', sa.Text(), nullable=False),
        sa.Column('bot_username', sa.String(100), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('last_error', sa.String(500), nullable=True),
        sa.Column('external_user_id', sa.BigInteger(), nullable=True),
        sa.Column('chat_id', sa.BigInteger(), nullable=True),
        sa.Column('pair_code_hash', sa.String(64), nullable=True),
        sa.Column('pair_expires_at', sa.DateTime(), nullable=True),
        sa.Column('conversation_id', sa.String(36), nullable=True),
        sa.Column('notify_schedules', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('last_update_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('user_id', 'channel', name='uq_channel_accounts_user_channel'),
    )


def downgrade() -> None:
    op.drop_table('channel_accounts')
    op.drop_column('conversations', 'channel')
