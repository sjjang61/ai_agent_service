"""wiki 지식 그래프: wiki_entries 노드 컬럼 + wiki_edges

Revision ID: t3a1b2c3d4e5
Revises: s2a1b2c3d4e5
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 't3a1b2c3d4e5'
down_revision: Union[str, None] = 's2a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('wiki_entries', sa.Column('node_type', sa.String(20), nullable=False, server_default='source'))
    op.create_index('ix_wiki_entries_node_type', 'wiki_entries', ['node_type'])
    op.add_column('wiki_entries', sa.Column('aliases', sa.JSON(), nullable=True))
    op.add_column('wiki_entries', sa.Column('auto_generated', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('wiki_entries', sa.Column('graph_hash', sa.String(40), nullable=True))
    op.add_column('wiki_entries', sa.Column('graph_status', sa.String(12), nullable=False, server_default=''))
    op.create_table(
        'wiki_edges',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('src_id', sa.String(36), nullable=False),
        sa.Column('dst_id', sa.String(36), nullable=False),
        sa.Column('relation', sa.String(60), nullable=False, server_default=''),
        sa.Column('kind', sa.String(12), nullable=False, server_default='link'),
        sa.Column('weight', sa.Float(), nullable=False, server_default='1'),
        sa.Column('origin_id', sa.String(36), nullable=True),
        sa.Column('evidence', sa.String(300), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('user_id', 'src_id', 'dst_id', 'relation', 'kind', name='uq_wiki_edge'),
    )
    op.create_index('ix_wiki_edges_user_src', 'wiki_edges', ['user_id', 'src_id'])
    op.create_index('ix_wiki_edges_user_dst', 'wiki_edges', ['user_id', 'dst_id'])


def downgrade() -> None:
    op.drop_table('wiki_edges')
    for c in ('graph_status', 'graph_hash', 'auto_generated', 'aliases'):
        op.drop_column('wiki_entries', c)
    op.drop_index('ix_wiki_entries_node_type', 'wiki_entries')
    op.drop_column('wiki_entries', 'node_type')
