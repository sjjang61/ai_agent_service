import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Index, Integer, String, Text, UniqueConstraint

from app.db.base import Base


def _now():
    return datetime.now(timezone.utc)


class SiteVertical(Base):
    """사이트 분야(쇼핑·영화·항공·호텔 …) 공통 지침. 분야에 속한 모든 사이트가 함께 쓴다."""

    __tablename__ = "site_verticals"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String(50), nullable=False, unique=True, index=True)  # shopping | movie | flight | hotel
    category = Column(String(30), nullable=True)  # 카테고리 key (agent/site_categories.py). 분야는 카테고리 아래의 상세 분류
    reference_skills = Column(String(300), nullable=True)  # 쉼표 구분. 사이트 분석이 참고할 스킬 이름(없으면 건너뜀)
    name = Column(String(100), nullable=False)
    keywords = Column(Text, nullable=False, default="")  # 쉼표 구분. 작업 문장에 나오면 이 분야 지침을 붙인다
    stop_words = Column(Text, nullable=False, default="")  # 쉼표 구분. 이 라벨의 버튼은 누르지 않는다 (결제 직전에 멈춘다)
    stop_urls = Column(Text, nullable=False, default="")  # 쉼표 구분. 이 문구가 주소에 있으면 이동하지 않는다
    body = Column(Text, nullable=False, default="")  # 에이전트에게 주는 공통 지침 (markdown)
    checklist = Column(Text, nullable=False, default="")  # 새 사이트를 분석할 때 확인할 항목 (markdown)
    spec = Column(JSON, nullable=True)  # 구조화: {inputs, flow, sample}. agent/site_spec.py 참고
    source = Column(String(20), nullable=False, default="seed")  # seed | ui
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class SiteCommon(Base):
    """웹사이트 분석 전체 공통 지침(분야·사이트와 무관하게 모든 브라우저 작업·분석에 붙는다). 행은 하나(key='common')."""

    __tablename__ = "site_common"

    key = Column(String(20), primary_key=True, default="common")
    body = Column(Text, nullable=False, default="")
    version = Column(Integer, nullable=False, default=1)
    source = Column(String(20), nullable=False, default="seed")  # seed | ui
    updated_by = Column(String(100), nullable=True)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class SiteProfile(Base):
    """사이트별 특성(요령). 분야 지침과 함께 브라우저 에이전트에게 주어진다."""

    __tablename__ = "site_profiles"
    __table_args__ = (UniqueConstraint("name", name="uq_site_profiles_name"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    vertical = Column(String(50), nullable=True, index=True)  # SiteVertical.key (분야가 없는 사이트도 있다)
    category = Column(String(30), nullable=True)  # 분야가 없는 사이트의 카테고리 key (분야가 있으면 분야의 카테고리를 따른다)
    reference_skills = Column(String(300), nullable=True)  # 쉼표 구분. 사이트 분석이 참고할 스킬 이름(없으면 건너뜀). 분야의 것과 합쳐 쓴다
    reference_commands = Column(JSON, nullable=True)  # [{skill, label, command}] 분석 전에 일회용 컨테이너에서 돌릴 조회 전용 스킬 명령(결과를 기준 데이터로 준다)
    domains = Column(Text, nullable=False, default="")  # 쉼표 구분. 하위 도메인도 맞는다
    aliases = Column(Text, nullable=False, default="")  # 쉼표 구분. 작업 문장에 나오면 시작할 때 붙인다
    body = Column(Text, nullable=False, default="")  # 에이전트에게 주는 사이트 요령 (구조화에 담기지 않는 예외·주의, markdown)
    spec = Column(JSON, nullable=True)  # 구조화: {entry, menus, inputs, flow, stop_point}. agent/site_spec.py 참고
    status = Column(String(20), nullable=False, default="verified")  # verified | draft | stale. draft 는 에이전트에게 주지 않는다
    verified_at = Column(String(10), nullable=True)  # YYYY-MM-DD
    enabled = Column(Boolean, nullable=False, default=True)
    source = Column(String(20), nullable=False, default="seed")  # seed | ui | analysis
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class SiteProfileRevision(Base):
    """분야·사이트를 저장할 때마다 남기는 스냅샷 (수정 이력과 되돌리기용). 저장한 뒤의 상태를 담는다."""

    __tablename__ = "site_profile_revisions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kind = Column(String(10), nullable=False)  # site | vertical
    ref = Column(String(50), nullable=False)  # 사이트 id(36) 또는 분야 key
    version = Column(Integer, nullable=False)
    snapshot = Column(JSON, nullable=False)
    source = Column(String(20), nullable=False, default="ui")  # seed | ui | analysis | restore
    author = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=_now, index=True)

    __table_args__ = (Index("ix_site_rev_ref", "kind", "ref", "version"),)


class SiteAnalysisRun(Base):
    """사이트 분석(초안 만들기)·재현 검증 한 번의 실행 기록. 진행 단계와 결과를 화면이 주기적으로 읽는다."""

    __tablename__ = "site_analysis_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    mode = Column(String(10), nullable=False)  # analyze | verify
    name = Column(String(100), nullable=False, index=True)  # 대상 사이트 이름 (저장 전 사이트일 수도 있다)
    vertical = Column(String(50), nullable=True)
    start_url = Column(String(500), nullable=False)
    scenario = Column(Text, nullable=False, default="")
    status = Column(String(12), nullable=False, default="running")  # running | succeeded | failed | cancelled
    browser_run = Column(String(16), nullable=True)  # 브라우저 스크린샷을 묶는 작업 태그
    steps = Column(JSON, nullable=True)  # [{id, desc, ok, brief, t0, t1}]
    draft_body = Column(Text, nullable=True)  # analyze: 만든 초안 / verify: 검증에 쓴 초안
    draft_spec = Column(JSON, nullable=True)  # 초안의 구조화 부분 (사이트 spec)
    inputs = Column(JSON, nullable=True)  # 이번 실행에 쓴 입력값 {입력키: 값}
    captcha_handoff = Column(Boolean, nullable=False, default=False)  # CAPTCHA 가 나오면 사용자에게 넘겨 해결을 기다린다
    clean_session = Column(Boolean, nullable=False, default=False)  # 내 앱 브라우저 대신 깨끗한 sandbox 브라우저에서 실행 (내 로그인·이전 검색 상태 없음)
    result = Column(JSON, nullable=True)  # verify: {passed, success, summary, issues, steps, seconds, loop_blocks}
    answer = Column(Text, nullable=True)  # 에이전트의 최종 답변 원문
    error = Column(Text, nullable=True)
    base_run_id = Column(String(36), nullable=True)  # verify 가 검증한 분석 실행
    created_at = Column(DateTime, default=_now, index=True)
    finished_at = Column(DateTime, nullable=True)


class BrowserBenchResult(Base):
    """브라우저 자동화 측정: 검증된 사이트 시나리오를 반복 실행한 결과 한 건 (scripts/browser_bench.py).
    같은 label 로 묶어 통과율·실패 원인·시간을 집계하고, label 끼리 비교해 개선 효과를 숫자로 확인한다."""

    __tablename__ = "browser_bench_results"
    __table_args__ = (Index("ix_bench_label_site", "label", "site_name"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    label = Column(String(100), nullable=False, index=True)  # 측정 묶음 이름 (예: baseline, after-heal)
    site_name = Column(String(100), nullable=False)
    vertical = Column(String(50), nullable=True)
    attempt = Column(Integer, nullable=False, default=1)
    run_id = Column(String(36), nullable=True)  # SiteAnalysisRun.id (단계별 기록은 거기에 있다)
    run_status = Column(String(20), nullable=False, default="")  # succeeded | failed | cancelled
    passed = Column(Boolean, nullable=False, default=False)
    success = Column(Boolean, nullable=False, default=False)
    seconds = Column(Integer, nullable=True)
    steps = Column(Integer, nullable=True)  # 브라우저 동작 수
    failed_steps = Column(Integer, nullable=True)
    loop_blocks = Column(Integer, nullable=True)
    tokens = Column(Integer, nullable=True)  # 모델이 알려 준 총 토큰 (모르면 NULL)
    heals = Column(Integer, nullable=True)  # 요소 번호 자동 복구 횟수
    flow = Column(JSON, nullable=True)  # [{key, title, status}]
    issues = Column(JSON, nullable=True)
    errors = Column(JSON, nullable=True)  # {오류 분류: 횟수}
    reasons = Column(JSON, nullable=True)  # 통과하지 못한 이유 분류 목록
    env = Column(JSON, nullable=True)  # {daemon: 데몬 버전, llm: 모델 종류}
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now)
