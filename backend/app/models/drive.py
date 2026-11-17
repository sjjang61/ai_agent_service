import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, Column, DateTime, ForeignKey, Index, String, UniqueConstraint

from app.db.base import Base


class DriveNode(Base):
    """Drive 의 폴더/파일 한 개. 폴더 트리는 DB 가 갖고, 파일 본문은 MinIO 비공개 버킷에 불투명한 키(drive/{user}/{node})로 둔다.
    그래서 이름 변경·이동은 이 행만 바꾸고 객체는 건드리지 않는다.

    - 사용자별 루트 폴더의 id 는 user_id 와 같다 (PK 라서 사용자당 하나가 보장된다). parent_id 가 NULL 인 노드는 루트뿐이다.
    - 한 폴더 안에서 이름은 유일하다. 대소문자·악센트를 구분하지 않는 DB collation(utf8mb4_unicode_ci)이 그대로 규칙이 된다.
    - 삭제는 휴지통 이동이다: trashed_at 과 trash_key(삭제된 묶음 id)를 채운다. 살아 있는 항목은 trash_key='' 이므로 삭제된 이름이 새 항목과 충돌하지 않는다.
    """

    __tablename__ = "drive_nodes"
    __table_args__ = (
        UniqueConstraint("user_id", "parent_id", "name", "trash_key", name="uq_drive_nodes_name"),
        Index("ix_drive_nodes_listing", "user_id", "parent_id", "trashed_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    parent_id = Column(String(36), ForeignKey("drive_nodes.id"), nullable=True)
    type = Column(String(10), nullable=False)  # folder | file
    name = Column(String(255), nullable=False)  # NFC 로 정규화한 표시 이름
    size_bytes = Column(BigInteger, nullable=False, default=0)  # 파일만
    mime = Column(String(127), nullable=True)
    sha256 = Column(String(64), nullable=True)
    storage_key = Column(String(255), nullable=True)  # 파일만: MinIO 객체 키
    source = Column(String(20), nullable=False, default="upload")  # upload | agent | sandbox | function
    source_ref = Column(JSON, nullable=True)  # {conversation_id, workspace_path} 등. 목록 조회에서는 읽지 않는다
    trashed_at = Column(DateTime, nullable=True)
    trash_root_id = Column(String(36), nullable=True)  # 한 번에 삭제된 묶음의 최상위 노드 (복원 단위)
    trash_key = Column(String(36), nullable=False, default="")  # 살아 있으면 '', 휴지통이면 trash_root_id
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class DriveUsage(Base):
    """사용자별 사용 용량 카운터 (휴지통 포함). 업로드가 한도를 동시에 통과하지 못하게 조건부 UPDATE 로 선점한다."""

    __tablename__ = "drive_usage"

    user_id = Column(String(36), ForeignKey("users.id"), primary_key=True)
    used_bytes = Column(BigInteger, nullable=False, default=0)
