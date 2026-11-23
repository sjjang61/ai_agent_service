"""웹사이트 분석: 브라우저 에이전트가 쓰는 분야 공통 지침과 사이트별 특성의 조회·편집. 모든 로그인 사용자가 편집할 수 있다 (플랫폼 공통)."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import site_categories
from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.site_profile import SiteProfile, SiteProfileRevision, SiteVertical
from app.models.user import User
from app.services import browser_bench as bench
from app.services import site_analysis_service as analysis
from app.services import site_profile_service as svc

router = APIRouter()


class CategoryOut(BaseModel):
    key: str
    name: str


class VerticalOut(BaseModel):
    key: str
    name: str
    category: Optional[str] = None
    reference_skills: Optional[str] = None
    keywords: str
    stop_words: str
    stop_urls: str
    body: str
    checklist: str
    spec: dict = {}
    source: str
    version: int
    updated_at: Optional[datetime] = None
    site_count: int = 0
    md: str = ""


class SiteOut(BaseModel):
    id: str
    name: str
    vertical: Optional[str] = None
    category: Optional[str] = None  # 분야가 없는 사이트의 카테고리
    reference_skills: Optional[str] = None
    domains: str
    aliases: str
    body: str
    spec: dict = {}
    status: str
    verified_at: Optional[str] = None
    enabled: bool
    source: str
    version: int
    updated_at: Optional[datetime] = None
    is_stale: bool = False
    md: str = ""


class ProfilesOut(BaseModel):
    categories: list[CategoryOut] = []
    verticals: list[VerticalOut]
    sites: list[SiteOut]
    stale_days: int


class VerticalIn(BaseModel):
    key: Optional[str] = None  # 만들 때만
    name: str
    category: Optional[str] = Field(default=None, description="카테고리 key. 보내지 않으면 지금 값을 유지한다")
    reference_skills: Optional[str] = Field(default=None, description="사이트 분석이 참고할 스킬 이름(쉼표). 보내지 않으면 지금 값을 유지, 빈 문자열이면 비운다")
    keywords: str = ""
    stop_words: str = ""
    stop_urls: str = ""
    body: str
    checklist: str = ""
    spec: Optional[dict] = Field(default=None, description="구조화(입력값·플로우·샘플). 비우면 지금 값을 유지한다")
    version: Optional[int] = Field(default=None, description="수정 시 마지막으로 본 버전 (다른 사용자가 먼저 고쳤는지 확인)")


class SiteIn(BaseModel):
    name: str
    vertical: Optional[str] = None
    category: Optional[str] = Field(default=None, description="분야가 없는 사이트의 카테고리 key. 보내지 않으면 지금 값을 유지한다")
    reference_skills: Optional[str] = Field(default=None, description="사이트 분석이 참고할 스킬 이름(쉼표). 보내지 않으면 지금 값을 유지, 빈 문자열이면 비운다")
    domains: str
    aliases: str = ""
    body: str = ""
    spec: Optional[dict] = Field(default=None, description="구조화(진입 주소·메뉴 지도·입력 방법·단계). 비우면 지금 값을 유지한다")
    status: str = "verified"
    verified_at: Optional[str] = None
    enabled: bool = True
    version: Optional[int] = None


class CommonOut(BaseModel):
    body: str
    version: int
    source: str
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None


class CommonIn(BaseModel):
    body: str = ""
    version: Optional[int] = Field(default=None, description="마지막으로 본 버전 (다른 사용자가 먼저 고쳤는지 확인)")


class PreviewOut(BaseModel):
    text: str


class RevisionOut(BaseModel):
    id: str
    version: int
    source: str
    author: Optional[str] = None
    created_at: Optional[datetime] = None
    snapshot: dict


def _author(user: User) -> str:
    return (getattr(user, "display_name", None) or getattr(user, "email", None) or user.id)[:100]


def _rev_out(r: SiteProfileRevision) -> RevisionOut:
    return RevisionOut(id=r.id, version=r.version, source=r.source, author=r.author, created_at=r.created_at, snapshot=r.snapshot or {})


def _vertical_out(row: SiteVertical, counts: dict) -> VerticalOut:
    return VerticalOut(
        key=row.key, name=row.name, category=row.category, reference_skills=row.reference_skills, keywords=row.keywords, stop_words=row.stop_words, stop_urls=row.stop_urls, body=row.body,
        checklist=row.checklist, spec=row.spec or {}, source=row.source, version=row.version, updated_at=row.updated_at,
        site_count=counts.get(row.key, 0), md=svc.vertical_md(row),
    )


def _site_out(row: SiteProfile) -> SiteOut:
    return SiteOut(
        id=row.id, name=row.name, vertical=row.vertical, category=row.category, reference_skills=row.reference_skills, domains=row.domains, aliases=row.aliases, body=row.body, spec=row.spec or {}, status=row.status,
        verified_at=row.verified_at, enabled=row.enabled, source=row.source, version=row.version, updated_at=row.updated_at,
        is_stale=svc.is_stale(row), md=svc.site_md(row),
    )


def _fail(e: svc.ProfileError):
    raise HTTPException(status_code=e.status, detail=e.detail)


def _common_out(row) -> CommonOut:
    return CommonOut(body=row.body, version=row.version, source=row.source, updated_by=row.updated_by, updated_at=row.updated_at)


@router.get("/common", response_model=CommonOut)
async def get_common(db: AsyncSession = Depends(get_session), _: User = Depends(get_current_user)):
    """모든 브라우저 작업·사이트 분석에 붙는 전체 공통 지침."""
    return _common_out(await svc.get_common(db))


@router.put("/common", response_model=CommonOut)
async def update_common(data: CommonIn, db: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    try:
        return _common_out(await svc.save_common(db, data.body, version=data.version, author=_author(user)))
    except svc.ProfileError as e:
        _fail(e)


@router.get("", response_model=ProfilesOut)
async def list_profiles(db: AsyncSession = Depends(get_session), _: User = Depends(get_current_user)):
    verticals, sites = await svc.list_all(db)
    counts: dict = {}
    for s in sites:
        if s.vertical:
            counts[s.vertical] = counts.get(s.vertical, 0) + 1
    return ProfilesOut(categories=[CategoryOut(key=k, name=n) for k, n in site_categories.CATEGORIES], verticals=[_vertical_out(v, counts) for v in verticals], sites=[_site_out(s) for s in sites], stale_days=svc.STALE_DAYS)


@router.post("/verticals", response_model=VerticalOut, status_code=201)
async def create_vertical(data: VerticalIn, db: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    try:
        return _vertical_out(await svc.save_vertical(db, data.model_dump(), author=_author(user)), {})
    except svc.ProfileError as e:
        _fail(e)


@router.put("/verticals/{key}", response_model=VerticalOut)
async def update_vertical(key: str, data: VerticalIn, db: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    try:
        row = await svc.save_vertical(db, data.model_dump(), key=key, version=data.version, author=_author(user))
        _, sites = await svc.list_all(db)
        return _vertical_out(row, {key: sum(1 for s in sites if s.vertical == key)})
    except svc.ProfileError as e:
        _fail(e)


@router.delete("/verticals/{key}", status_code=204)
async def delete_vertical(key: str, db: AsyncSession = Depends(get_session), _: User = Depends(get_current_user)):
    try:
        await svc.delete_vertical(db, key)
    except svc.ProfileError as e:
        _fail(e)


@router.post("/sites", response_model=SiteOut, status_code=201)
async def create_site(data: SiteIn, db: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    try:
        return _site_out(await svc.save_site(db, data.model_dump(), author=_author(user)))
    except svc.ProfileError as e:
        _fail(e)


@router.put("/sites/{site_id}", response_model=SiteOut)
async def update_site(site_id: str, data: SiteIn, db: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    try:
        return _site_out(await svc.save_site(db, data.model_dump(), site_id=site_id, version=data.version, author=_author(user)))
    except svc.ProfileError as e:
        _fail(e)


@router.delete("/sites/{site_id}", status_code=204)
async def delete_site(site_id: str, db: AsyncSession = Depends(get_session), _: User = Depends(get_current_user)):
    try:
        await svc.delete_site(db, site_id)
    except svc.ProfileError as e:
        _fail(e)


@router.post("/sites/preview", response_model=PreviewOut)
async def preview_site(data: SiteIn, db: AsyncSession = Depends(get_session), _: User = Depends(get_current_user)):
    """저장하기 전에, 지금 입력한 내용이 에이전트에게 어떻게 주어지는지 보여 준다."""
    vertical = None
    if data.vertical:
        verticals, _s = await svc.list_all(db)
        vertical = next((v for v in verticals if v.key == data.vertical.strip().lower()), None)
    try:
        spec = svc.clean_spec_for_preview(data.spec)
    except svc.ProfileError as e:
        _fail(e)
    site = SiteProfile(name=data.name.strip() or "(이름 없음)", vertical=data.vertical, domains=data.domains, aliases=data.aliases,
                       body=data.body.strip(), verified_at=data.verified_at, spec=spec)
    return PreviewOut(text=svc.preview_text(site, vertical))


@router.get("/sites/{site_id}/revisions", response_model=list[RevisionOut])
async def site_revisions(site_id: str, db: AsyncSession = Depends(get_session), _: User = Depends(get_current_user)):
    return [_rev_out(r) for r in await svc.list_revisions(db, "site", site_id)]


@router.post("/sites/{site_id}/revisions/{rev_id}/restore", response_model=SiteOut)
async def restore_site_revision(site_id: str, rev_id: str, db: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    try:
        return _site_out(await svc.restore_site(db, site_id, rev_id, author=_author(user)))
    except svc.ProfileError as e:
        _fail(e)


@router.get("/verticals/{key}/revisions", response_model=list[RevisionOut])
async def vertical_revisions(key: str, db: AsyncSession = Depends(get_session), _: User = Depends(get_current_user)):
    return [_rev_out(r) for r in await svc.list_revisions(db, "vertical", key)]


@router.post("/verticals/{key}/revisions/{rev_id}/restore", response_model=VerticalOut)
async def restore_vertical_revision(key: str, rev_id: str, db: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    try:
        row = await svc.restore_vertical(db, key, rev_id, author=_author(user))
        _, sites = await svc.list_all(db)
        return _vertical_out(row, {key: sum(1 for s in sites if s.vertical == key)})
    except svc.ProfileError as e:
        _fail(e)


# ── 사이트 분석·재현 검증 ───────────────────────────────────────
class AnalysisIn(BaseModel):
    mode: str = Field(description="analyze(초안 만들기) | verify(초안으로 시나리오 재현)")
    name: str
    vertical: Optional[str] = None
    start_url: str
    scenario: str
    draft_body: Optional[str] = Field(default=None, description="verify: 시험할 요령 초안")
    current_body: Optional[str] = Field(default=None, description="analyze: 지금 저장된(편집 중인) 요령. 맞는 것은 유지하고 고치게 한다")
    draft_spec: Optional[dict] = Field(default=None, description="verify: 시험할 구조화 초안(사이트 spec). analyze: 지금 편집 중인 spec")
    inputs: Optional[dict] = Field(default=None, description="시나리오에 쓸 입력값 {입력키: 값}. 비운 항목은 분야의 샘플값을 쓴다")
    clean_session: bool = Field(default=False, description="내 앱 브라우저 대신 깨끗한 서버(sandbox) 브라우저에서 실행한다. 내 로그인·이전 검색 상태가 섞이지 않는다 (captcha_handoff 와 함께 쓸 수 없다)")
    captcha_handoff: bool = Field(default=False, description="CAPTCHA 가 나오면 우회하지 않고 사용자에게 넘겨 해결을 기다린다 (사용자가 화면 앞에 있을 때만 켠다)")
    base_run_id: Optional[str] = None


class AnalysisStep(BaseModel):
    id: Optional[str] = None
    action: str = ""
    desc: str = ""
    url: str = ""
    ok: Optional[bool] = None
    brief: str = ""
    t0: Optional[int] = None
    t1: Optional[int] = None


class AnalysisOut(BaseModel):
    id: str
    mode: str
    name: str
    vertical: Optional[str] = None
    start_url: str
    scenario: str
    status: str
    browser_run: Optional[str] = None
    steps: list[AnalysisStep] = []
    draft_body: Optional[str] = None
    draft_spec: Optional[dict] = None
    inputs: Optional[dict] = None
    captcha_handoff: bool = False
    clean_session: bool = False
    result: Optional[dict] = None
    answer: Optional[str] = None
    error: Optional[str] = None
    base_run_id: Optional[str] = None
    created_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


def _run_out(r) -> AnalysisOut:
    return AnalysisOut(
        id=r.id, mode=r.mode, name=r.name, vertical=r.vertical, start_url=r.start_url, scenario=r.scenario, status=r.status,
        browser_run=r.browser_run, steps=[AnalysisStep(**{k: v for k, v in s.items() if k in AnalysisStep.model_fields}) for s in (r.steps or [])],
        draft_body=r.draft_body, draft_spec=r.draft_spec, inputs=r.inputs, captcha_handoff=bool(r.captcha_handoff), clean_session=bool(r.clean_session), result=r.result, answer=r.answer, error=r.error, base_run_id=r.base_run_id,
        created_at=r.created_at, finished_at=r.finished_at,
    )


def _afail(e: analysis.AnalysisError):
    raise HTTPException(status_code=e.status, detail=e.detail)


@router.post("/analysis/runs", response_model=AnalysisOut, status_code=201)
async def start_analysis(data: AnalysisIn, db: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    """사이트 분석(초안 만들기) 또는 재현 검증을 백그라운드로 시작한다. 한 사용자가 동시에 하나만 실행할 수 있다."""
    try:
        return _run_out(await analysis.start(db, user.id, data.model_dump()))
    except analysis.AnalysisError as e:
        _afail(e)


@router.get("/analysis/runs", response_model=list[AnalysisOut])
async def list_analysis(name: Optional[str] = None, limit: int = 10, db: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    return [_run_out(r) for r in await analysis.list_runs(db, user.id, name, limit)]


@router.get("/analysis/runs/{run_id}", response_model=AnalysisOut)
async def get_analysis(run_id: str, db: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    try:
        return _run_out(await analysis.get_run(db, user.id, run_id))
    except analysis.AnalysisError as e:
        _afail(e)


@router.post("/analysis/runs/{run_id}/cancel", response_model=AnalysisOut)
async def cancel_analysis(run_id: str, db: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    try:
        return _run_out(await analysis.cancel(db, user.id, run_id))
    except analysis.AnalysisError as e:
        _afail(e)


# ── 브라우저 자동화 측정 결과 (scripts/browser_bench.py 가 쌓는다. 읽기 전용) ─────────────
@router.get("/bench/labels")
async def bench_labels(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """측정 묶음(label) 목록: 실행 수·통과율·마지막 실행 시각, 최근 순."""
    return await bench.list_labels(db)


@router.get("/bench/summary")
async def bench_summary(label: Optional[str] = None, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """한 묶음의 집계: 전체·사이트별 통과율, 불안정한 사이트, 동작 오류 분류, 통과 못한 이유, 평균 시간·동작·토큰. label 이 없으면 가장 최근 묶음."""
    if not label:
        labels = await bench.list_labels(db)
        if not labels:
            raise HTTPException(status_code=404, detail="측정 결과가 없습니다")
        label = labels[0]["label"]
    rows = await bench.load_results(db, label)
    if not rows:
        raise HTTPException(status_code=404, detail="측정 결과를 찾을 수 없습니다")
    return {"label": label, **bench.aggregate(rows)}
