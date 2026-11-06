"""token_usages (중복 정의 자리표시 — 병합 충돌 정리)

b2c3d4e5f6a1 이 이미 token_usages 를 만든다. 예전 브랜치(llm_wiki)가 같은 테이블을 이 id 로 만들었고
cf4a817a7c8f(위키)가 이 id 를 down_revision 으로 쓰므로, 체인을 깨지 않도록 아무 일도 하지 않는 리비전으로 남긴다.

Revision ID: b2c3d4e5f6g7
Revises: b2c3d4e5f6a1
"""
from typing import Sequence, Union

revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, None] = 'b2c3d4e5f6a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
