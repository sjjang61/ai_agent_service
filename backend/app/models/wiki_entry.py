"""WikiEntry model for personal wiki storage."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    Boolean,
    Float,
    Index,
    UniqueConstraint,
)

from app.db.base import Base


class WikiEntry(Base):
    """Personal wiki entries saved from chat responses."""

    __tablename__ = "wiki_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Core content
    title = Column(String(200), nullable=False)  # User-defined title
    content = Column(Text, nullable=False)       # 위키 문서 본문 (마크다운). AI 가 정리한 문서이거나, 정리 없이 저장한 원문
    summary = Column(String(500), nullable=True)  # 한두 문장 요약
    source_text = Column(Text, nullable=True)     # 정리 전 원문 (사용자가 선택한 텍스트)
    links = Column(JSON, default=list)            # 이 문서가 연결한 다른 위키 문서 id 목록 (역링크는 조회할 때 계산)

    # 지식 그래프: 문서 = 노드. source(저장한 원본 지식) | entity(개체) | concept(개념) | overview | other
    node_type = Column(String(20), nullable=False, default="source", index=True)
    aliases = Column(JSON, default=list)  # 같은 대상의 다른 이름 (엔티티 판정에 쓴다)
    auto_generated = Column(Boolean, nullable=False, default=False)  # AI 가 만든 스텁 문서. 목록에서는 기본 숨김
    graph_hash = Column(String(40), nullable=True)  # 마지막으로 지식화한 본문의 해시
    graph_status = Column(String(12), nullable=False, default="")  # '' | pending | done | failed

    # Metadata
    category = Column(String(50), nullable=False, default="general")  # general | work | learning | reference
    tags = Column(JSON, default=list)  # ["python", "tutorial", "api"]

    # Source tracking (optional - for future "view original" feature)
    source_message_id = Column(String(36), nullable=True)  # FK to messages.id
    source_conversation_id = Column(String(36), nullable=True)  # FK to conversations.id

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class WikiEdge(Base):
    """위키 문서(노드) 사이의 연결. kind: link(본문 [[ ]]/사용자 연결) | mentions(원본→개체) | extracted(개체 사이 관계) | similar."""

    __tablename__ = "wiki_edges"
    __table_args__ = (
        UniqueConstraint("user_id", "src_id", "dst_id", "relation", "kind", name="uq_wiki_edge"),
        Index("ix_wiki_edges_user_src", "user_id", "src_id"),
        Index("ix_wiki_edges_user_dst", "user_id", "dst_id"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    src_id = Column(String(36), nullable=False)
    dst_id = Column(String(36), nullable=False)
    relation = Column(String(60), nullable=False, default="")
    kind = Column(String(12), nullable=False, default="link")
    weight = Column(Float, nullable=False, default=1.0)
    origin_id = Column(String(36), nullable=True)  # 이 간선을 만든 원본 문서 (재지식화할 때 이 문서가 만든 간선만 지운다)
    evidence = Column(String(300), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
