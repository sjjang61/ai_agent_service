"""merge: RAG 테이블 브랜치(c3d4e5f6a1b2)와 본 체인(s1a1b2c3d4e5)을 하나로

Revision ID: s2a1b2c3d4e5
Revises: s1a1b2c3d4e5, c3d4e5f6a1b2
"""
from typing import Sequence, Union

revision: str = 's2a1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = ('s1a1b2c3d4e5', 'c3d4e5f6a1b2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
