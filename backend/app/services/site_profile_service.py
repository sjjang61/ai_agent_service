"""사이트 요령(분야 공통 지침 + 사이트별 특성)의 DB 저장·시드·로딩.

원본은 DB 이고, 저장소의 md 파일(agent/site_tips/)은 시드(DB 에 없는 것만 채움)와 내보내기에 쓴다.
런타임은 DB 내용을 agent/site_tips 의 메모리 캐시로 읽어 쓰므로, 저장하거나 시드한 뒤에는 refresh() 로 캐시를 갱신한다.
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import json

from app.agent import site_categories, site_spec, site_tips
from app.models.site_profile import SiteCommon, SiteProfile, SiteProfileRevision, SiteVertical

logger = logging.getLogger(__name__)

# 에이전트에게 주는 상태. draft(분석 초안)는 검증 전이라 주지 않는다. stale(오래됨)은 줄 수 있다.
USABLE_STATUSES = ("verified", "stale")


def _join(items) -> str:
    return ", ".join(items)


async def seed_from_files(db: AsyncSession) -> dict:
    """저장소 md 파일 중 DB 에 없는 분야·사이트를 추가한다. 이미 있는 것(UI 에서 고친 것 포함)은 덮어쓰지 않는다."""
    added = {"verticals": 0, "sites": 0}
    have_v = {r for (r,) in (await db.execute(select(SiteVertical.key))).all()}
    for v in site_tips.file_verticals():
        if v.key and v.key not in have_v:
            db.add(SiteVertical(key=v.key, name=v.name, keywords=_join(v.keywords), stop_words=_join(v.stop_words),
                                stop_urls=_join(v.stop_urls), body=v.body, checklist=v.checklist, spec=v.spec or None, category=v.category or None, reference_skills=_join(v.skills) or None, source="seed"))
            added["verticals"] += 1
    # 이름이 바뀐 시드(한 사이트가 여러 분야를 갖게 되며 '아고다' → '아고다 · 항공권'): 화면에서 고치지 않은 행은 제자리에서 이름만 바꾼다
    renamed = {"아고다": "아고다 · 항공권", "네이버 플레이스": "네이버 예약"}
    have_names = {r for (r,) in (await db.execute(select(SiteProfile.name))).all()}
    for old, new in renamed.items():
        row = (await db.execute(select(SiteProfile).where(SiteProfile.name == old, SiteProfile.source == "seed"))).scalar_one_or_none()
        if row is not None and new not in have_names:
            row.name = new
    await db.flush()
    have_s = {r for (r,) in (await db.execute(select(SiteProfile.name))).all()}
    for t in site_tips.file_tips():
        if t.name and t.name not in have_s:
            db.add(SiteProfile(name=t.name, vertical=t.vertical or None, domains=_join(t.domains), aliases=_join(t.aliases),
                               body=t.body, spec=t.spec or None, status=t.status if t.status in STATUSES else "verified", verified_at=t.verified or None,
                               category=(None if t.vertical else (t.category or None)), reference_skills=_join(t.skills) or None, source="seed"))
            added["sites"] += 1
    # 구조화 기능이 생기기 전에 시드된 항목: 화면에서 고친 적 없고(source=seed) spec 이 비어 있으면 md 의 spec 을 채운다
    files_v = {v.key: v for v in site_tips.file_verticals()}
    for row in (await db.execute(select(SiteVertical).where(SiteVertical.source == "seed"))).scalars().all():
        if not row.spec and files_v.get(row.key) and files_v[row.key].spec:
            row.spec = files_v[row.key].spec
            added["verticals"] += 1
    files_s = {t.name: t for t in site_tips.file_tips()}
    for row in (await db.execute(select(SiteProfile).where(SiteProfile.source == "seed"))).scalars().all():
        if not row.spec and files_s.get(row.name) and files_s[row.name].spec:
            row.spec = files_s[row.name].spec
            added["sites"] += 1
    if (await db.get(SiteCommon, COMMON_KEY)) is None:  # 전체 공통 지침: 처음 한 번만 md 로 시드한다(이후 화면에서 고친 것은 덮어쓰지 않는다)
        db.add(SiteCommon(key=COMMON_KEY, body=site_tips.file_common(), source="seed"))
        await db.flush()
    # 카테고리가 생기기 전에 만든 항목: 비어 있는 것만 md 의 카테고리로 채운다 (이미 정한 값은 덮어쓰지 않는다)
    for row in (await db.execute(select(SiteVertical).where(SiteVertical.category.is_(None)))).scalars().all():
        if files_v.get(row.key) and files_v[row.key].category:
            row.category = files_v[row.key].category
            added["verticals"] += 1
    for row in (await db.execute(select(SiteProfile).where(SiteProfile.category.is_(None), SiteProfile.vertical.is_(None)))).scalars().all():
        if files_s.get(row.name) and files_s[row.name].category:
            row.category = files_s[row.name].category
            added["sites"] += 1
    # 참고 스킬이 생기기 전에 만든 항목: 비어 있는 것만 md 로 채운다
    for row in (await db.execute(select(SiteVertical).where(SiteVertical.reference_skills.is_(None)))).scalars().all():
        if files_v.get(row.key) and files_v[row.key].skills:
            row.reference_skills = _join(files_v[row.key].skills)
    for row in (await db.execute(select(SiteProfile).where(SiteProfile.reference_skills.is_(None)))).scalars().all():
        if files_s.get(row.name) and files_s[row.name].skills:
            row.reference_skills = _join(files_s[row.name].skills)
    await db.commit()
    return added


def to_vertical(row: SiteVertical) -> site_tips.Vertical:
    return site_tips.Vertical(
        key=row.key, name=row.name, keywords=site_tips._csv(row.keywords), stop_words=site_tips._csv(row.stop_words),
        stop_urls=site_tips._csv(row.stop_urls), body=row.body or "", checklist=row.checklist or "", spec=row.spec or {}, category=row.category or "",
        skills=site_tips._csv(row.reference_skills),
    )


def to_tip(row: SiteProfile) -> site_tips.SiteTip:
    return site_tips.SiteTip(
        name=row.name, domains=site_tips._csv(row.domains), aliases=site_tips._csv(row.aliases), verified=row.verified_at or "",
        body=row.body or "", vertical=(row.vertical or "").lower(), spec=row.spec or {}, category=row.category or "",
        skills=site_tips._csv(row.reference_skills),
    )


async def refresh(db: AsyncSession) -> None:
    """DB 의 분야·사이트(사용 가능한 것만)를 런타임 캐시에 올린다."""
    verticals = (await db.execute(select(SiteVertical).order_by(SiteVertical.key))).scalars().all()
    sites = (await db.execute(
        select(SiteProfile).where(SiteProfile.enabled.is_(True), SiteProfile.status.in_(USABLE_STATUSES)).order_by(SiteProfile.name)
    )).scalars().all()
    all_rows = (await db.execute(select(SiteProfile))).scalars().all()
    states = [site_tips.SiteState(name=r.name, domains=site_tips._csv(r.domains), aliases=site_tips._csv(r.aliases), enabled=bool(r.enabled))
              for r in all_rows if r.domains.strip()]
    common = await db.get(SiteCommon, COMMON_KEY)
    site_tips.set_cache([to_vertical(v) for v in verticals], [to_tip(s) for s in sites if s.domains.strip()], states, common=common.body if common is not None else None)


async def init() -> None:
    """서버 시작 때: 시드한 뒤 캐시를 채운다. 실패해도 서버는 md 파일 기본값으로 계속 동작한다."""
    from app.db.session import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            added = await seed_from_files(db)
            await refresh(db)
        if added["verticals"] or added["sites"]:
            logger.info("[site_profiles] 시드: 분야 %d, 사이트 %d", added["verticals"], added["sites"])
    except Exception:
        site_tips.clear_cache()
        logger.exception("[site_profiles] DB 에서 불러오지 못해 md 파일 기본값을 사용합니다")


# ── 조회·편집 (화면용) ─────────────────────────────────────────
import re
from datetime import date, datetime, timezone
from typing import Optional

COMMON_KEY = "common"
STALE_DAYS = 30  # 확인한 지 이 일수가 지나면 화면에서 '오래됨'으로 표시한다 (에이전트에게는 계속 준다)
STATUSES = ("verified", "draft", "stale")
_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,49}$")


class ProfileError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def normalize_domains(raw: str) -> str:
    """'https://www.Danawa.com/x, search.danawa.com' → 'danawa.com, search.danawa.com' (스킴·경로·포트·www 제거, 중복 제거)."""
    out: list[str] = []
    for tok in re.split(r"[,\s]+", raw or ""):
        tok = re.sub(r"^[a-z]+://", "", tok.strip().lower()).split("/")[0].split(":")[0].removeprefix("www.")
        if tok and tok not in out:
            if not re.fullmatch(r"[a-z0-9]([a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}", tok):
                raise ProfileError(400, f"도메인 형식이 올바르지 않습니다: {tok}")
            out.append(tok)
    return ", ".join(out)


def normalize_csv(raw: str) -> str:
    out: list[str] = []
    for tok in (raw or "").replace("\n", ",").split(","):
        tok = tok.strip()
        if tok and tok.lower() not in [o.lower() for o in out]:
            out.append(tok)
    return ", ".join(out)


def is_stale(row: SiteProfile, today: Optional[date] = None) -> bool:
    if row.status == "stale":
        return True
    if row.status != "verified" or not row.verified_at:
        return False
    try:
        return ((today or date.today()) - date.fromisoformat(row.verified_at)).days > STALE_DAYS
    except ValueError:
        return False


def _spec_fence(spec) -> str:
    return f"```spec\n{json.dumps(spec, ensure_ascii=False, indent=2)}\n```\n\n" if spec else ""


def site_md(row: SiteProfile) -> str:
    head = [f"name: {row.name}", f"domains: {row.domains}"]
    if row.vertical:
        head.append(f"vertical: {row.vertical}")
    elif row.category:
        head.append(f"category: {row.category}")  # 분야가 없는 사이트만 자기 카테고리를 갖는다
    if row.aliases:
        head.append(f"aliases: {row.aliases}")
    if row.reference_skills:
        head.append(f"skills: {row.reference_skills}")
    if row.status != "verified":
        head.append(f"status: {row.status}")  # draft(분석 전)·stale. 생략하면 verified 로 시드되므로 내보낼 때 빠뜨리면 안 된다
    head.append(f"verified: {row.verified_at or ''}")
    return "---\n" + "\n".join(head) + "\n---\n" + _spec_fence(row.spec) + (row.body or "").strip() + "\n"


def vertical_md(row: SiteVertical) -> str:
    head = [f"key: {row.key}", f"name: {row.name}"] + ([f"category: {row.category}"] if row.category else []) + ([f"skills: {row.reference_skills}"] if row.reference_skills else []) + [f"keywords: {row.keywords}", f"stop_words: {row.stop_words}", f"stop_urls: {row.stop_urls}"]
    body = _spec_fence(row.spec) + (row.body or "").strip()
    if (row.checklist or "").strip():
        body += f"\n\n{site_tips.CHECKLIST_HEADING}\n{row.checklist.strip()}"
    return "---\n" + "\n".join(head) + "\n---\n" + body + "\n"


def preview_text(site: SiteProfile, vertical: Optional[SiteVertical]) -> str:
    """이 사이트의 요령이 에이전트에게 주어지는 모습 (분야 지침 + 사이트 요령)."""
    parts = []
    if vertical is not None:
        parts.append(to_vertical(vertical).block())
    parts.append(to_tip(site).block(vspec=(vertical.spec or {}) if vertical is not None else None))
    return "\n\n".join(parts)


async def get_common(db: AsyncSession) -> SiteCommon:
    row = await db.get(SiteCommon, COMMON_KEY)
    if row is None:  # 시드 전(테스트 등): md 내용으로 만든다
        row = SiteCommon(key=COMMON_KEY, body=site_tips.file_common(), source="seed", version=1)
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


async def save_common(db: AsyncSession, body: str, version: Optional[int] = None, author: Optional[str] = None) -> SiteCommon:
    """전체 공통 지침을 고친다. 비워도 된다(공통 지침 없음). 저장하면 런타임 캐시를 갱신한다."""
    row = await get_common(db)
    _check_version(row, version)
    text = (body or "").strip()
    if len(text) > 4000:
        raise ProfileError(400, "전체 공통 지침은 4000자 이내로 입력하세요 (모든 브라우저 작업의 지침에 붙습니다)")
    row.body, row.source, row.updated_by, row.version = text, "ui", author, row.version + 1
    row.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(row)
    await refresh(db)
    return row


async def list_all(db: AsyncSession) -> tuple[list[SiteVertical], list[SiteProfile]]:
    verticals = (await db.execute(select(SiteVertical).order_by(SiteVertical.name))).scalars().all()
    sites = (await db.execute(select(SiteProfile).order_by(SiteProfile.name))).scalars().all()
    return list(verticals), list(sites)


async def _vertical(db: AsyncSession, key: str) -> SiteVertical:
    row = (await db.execute(select(SiteVertical).where(SiteVertical.key == key))).scalar_one_or_none()
    if row is None:
        raise ProfileError(404, "분야를 찾을 수 없습니다")
    return row


async def _site(db: AsyncSession, site_id: str) -> SiteProfile:
    row = await db.get(SiteProfile, site_id)
    if row is None:
        raise ProfileError(404, "사이트를 찾을 수 없습니다")
    return row


def _check_version(row, version: Optional[int]) -> None:
    if version is not None and version != row.version:
        raise ProfileError(409, "다른 사용자가 먼저 수정했습니다. 새로고침한 뒤 다시 시도하세요")


def _name(raw: str) -> str:
    name = (raw or "").strip()
    if not name or len(name) > 100:
        raise ProfileError(400, "이름은 1~100자로 입력하세요")
    return name


async def _check_domains(db: AsyncSession, domains: str, own_id: Optional[str], vertical: Optional[str] = None) -> None:
    """같은 도메인은 분야가 다를 때만 겹칠 수 있다 (한 사이트가 여러 분야를 가질 때 '아고다 · 항공권', '아고다 · 호텔' 처럼 분야마다 한 행)."""
    if not domains:
        raise ProfileError(400, "도메인을 하나 이상 입력하세요")
    mine = set(domains.split(", "))
    for other in (await db.execute(select(SiteProfile))).scalars().all():
        shared = mine & {d.strip() for d in other.domains.split(",") if d.strip()}
        if other.id != own_id and shared and (other.vertical or None) == (vertical or None):
            raise ProfileError(409, f"같은 분야에서 이미 다른 사이트({other.name})가 쓰는 도메인입니다: {', '.join(sorted(shared))}. 한 사이트가 여러 분야를 가지면 분야마다 따로 만드세요")


async def _check_name_free(db: AsyncSession, name: str, own_id: Optional[str]) -> None:
    other = (await db.execute(select(SiteProfile).where(SiteProfile.name == name))).scalar_one_or_none()
    if other is not None and other.id != own_id:
        raise ProfileError(409, "같은 이름의 사이트가 이미 있습니다")


async def _check_vertical_ref(db: AsyncSession, key: Optional[str]) -> Optional[str]:
    key = (key or "").strip().lower() or None
    if key is not None:
        await _vertical(db, key)
    return key


def clean_spec_for_preview(raw) -> dict:
    try:
        return site_spec.clean_site(raw)
    except site_spec.SpecError as e:
        raise ProfileError(400, str(e))


def _spec(data: dict, row, clean) -> Optional[dict]:
    """요청에 spec 이 있으면 검증해 새 값을, 없으면 지금 값을 유지한다 (spec 을 모르는 이전 화면이 저장해도 지워지지 않게)."""
    if "spec" not in data:
        return row.spec if row is not None else None
    try:
        return clean(data["spec"]) or None
    except site_spec.SpecError as e:
        raise ProfileError(400, str(e))


def _category(data: dict, row) -> Optional[str]:
    """요청에 category 가 있으면 검증해 새 값을, 없으면 지금 값을 유지한다 (카테고리를 모르는 이전 화면이 저장해도 지워지지 않게)."""
    if data.get("category") is None:  # 보내지 않았다(None): 지금 값을 유지. 비우려면 ''를 보낸다
        return row.category if row is not None else None
    try:
        return site_categories.normalize(data["category"]) or None
    except ValueError as e:
        raise ProfileError(400, str(e))


def _ref_skills(data: dict, row) -> Optional[str]:
    """참고 스킬 이름 목록(쉼표). 보내지 않으면(None) 지금 값을 유지하고, 빈 문자열이면 비운다."""
    if data.get("reference_skills") is None:
        return row.reference_skills if row is not None else None
    names = normalize_csv(data["reference_skills"])
    if len(names) > 300:
        raise ProfileError(400, "참고 스킬은 300자 이내로 입력하세요")
    return names  # 비우면 ''(None 이 아니다): 다시 시작할 때 md 로 채워지지 않게


def _status(raw: str) -> str:
    if raw not in STATUSES:
        raise ProfileError(400, "상태가 올바르지 않습니다")
    return raw


def _verified_at(raw: Optional[str]) -> Optional[str]:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        date.fromisoformat(raw)
    except ValueError:
        raise ProfileError(400, "확인일은 YYYY-MM-DD 형식이어야 합니다")
    return raw


async def save_site(db: AsyncSession, data: dict, site_id: Optional[str] = None, version: Optional[int] = None,
                    author: Optional[str] = None, source: str = "ui") -> SiteProfile:
    """사이트 요령을 만들거나 고친다. 저장하면 런타임 캐시를 갱신한다."""
    row = await _site(db, site_id) if site_id else None
    if row is not None:
        _check_version(row, version)
    name = _name(data.get("name", ""))
    domains = normalize_domains(data.get("domains", ""))
    await _check_name_free(db, name, row.id if row else None)
    vertical = await _check_vertical_ref(db, data.get("vertical"))
    await _check_domains(db, domains, row.id if row else None, vertical)
    status = _status(data.get("status") or "verified")
    verified_at = _verified_at(data.get("verified_at"))
    if status == "verified" and not verified_at:
        verified_at = date.today().isoformat()
    fields = dict(
        name=name, vertical=vertical, domains=domains, aliases=normalize_csv(data.get("aliases", "")),
        body=(data.get("body") or "").strip(), status=status, verified_at=verified_at, enabled=bool(data.get("enabled", True)),
        spec=_spec(data, row, site_spec.clean_site), category=None if vertical else _category(data, row),  # 분야가 있으면 분야의 카테고리를 따른다
        reference_skills=_ref_skills(data, row),
    )
    before = None
    if row is None:
        row = SiteProfile(**fields, source=source)
        db.add(row)
        await db.flush()
    else:
        before = snapshot_of(row)
        for k, v in fields.items():
            setattr(row, k, v)
        row.source, row.version = source, row.version + 1
        row.updated_at = datetime.now(timezone.utc)
    await _record(db, row, author, source, before)
    await db.commit()
    await db.refresh(row)
    await refresh(db)
    return row


async def _drop_revisions(db: AsyncSession, kind: str, ref: str) -> None:
    for rev in (await db.execute(select(SiteProfileRevision).where(SiteProfileRevision.kind == kind, SiteProfileRevision.ref == ref))).scalars().all():
        await db.delete(rev)


async def delete_site(db: AsyncSession, site_id: str) -> None:
    await db.delete(await _site(db, site_id))
    await _drop_revisions(db, "site", site_id)
    await db.commit()
    await refresh(db)


async def save_vertical(db: AsyncSession, data: dict, key: Optional[str] = None, version: Optional[int] = None,
                        author: Optional[str] = None, source: str = "ui") -> SiteVertical:
    row = await _vertical(db, key) if key else None
    if row is not None:
        _check_version(row, version)
    new_key = (data.get("key") or "").strip().lower() if row is None else row.key  # 키는 사이트가 참조하므로 만든 뒤에는 바꾸지 않는다
    if row is None:
        if not _KEY_RE.match(new_key):
            raise ProfileError(400, "분야 키는 영문 소문자로 시작하는 2~50자의 영문 소문자·숫자·밑줄이어야 합니다")
        if (await db.execute(select(SiteVertical).where(SiteVertical.key == new_key))).scalar_one_or_none() is not None:
            raise ProfileError(409, "같은 키의 분야가 이미 있습니다")
    fields = dict(
        name=_name(data.get("name", "")), keywords=normalize_csv(data.get("keywords", "")), stop_words=normalize_csv(data.get("stop_words", "")),
        stop_urls=normalize_csv(data.get("stop_urls", "")), body=(data.get("body") or "").strip(), checklist=(data.get("checklist") or "").strip(),
        spec=_spec(data, row, site_spec.clean_vertical), category=_category(data, row), reference_skills=_ref_skills(data, row),
    )
    if not fields["body"]:
        raise ProfileError(400, "공통 지침을 입력하세요")
    before = None
    if row is None:
        row = SiteVertical(key=new_key, **fields, source=source)
        db.add(row)
        await db.flush()
    else:
        before = snapshot_of(row)
        for k, v in fields.items():
            setattr(row, k, v)
        row.source, row.version = source, row.version + 1
        row.updated_at = datetime.now(timezone.utc)
    await _record(db, row, author, source, before)
    await db.commit()
    await db.refresh(row)
    await refresh(db)
    return row


async def delete_vertical(db: AsyncSession, key: str) -> None:
    row = await _vertical(db, key)
    used = (await db.execute(select(SiteProfile.name).where(SiteProfile.vertical == key))).scalars().all()
    if used:
        raise ProfileError(409, f"이 분야를 쓰는 사이트가 있어 삭제할 수 없습니다: {', '.join(used[:5])}")
    await db.delete(row)
    await _drop_revisions(db, "vertical", key)
    await db.commit()
    await refresh(db)


# ── 수정 이력 ─────────────────────────────────────────────────
MAX_REVISIONS = 50  # 항목마다 남기는 이력 수 (넘으면 오래된 것부터 지운다)
SITE_FIELDS = ("name", "vertical", "category", "reference_skills", "domains", "aliases", "body", "status", "verified_at", "enabled", "spec")
VERTICAL_FIELDS = ("name", "category", "reference_skills", "keywords", "stop_words", "stop_urls", "body", "checklist", "spec")


def snapshot_of(row) -> dict:
    fields = SITE_FIELDS if isinstance(row, SiteProfile) else VERTICAL_FIELDS
    return {k: getattr(row, k) for k in fields}


async def _record(db: AsyncSession, row, author: Optional[str], source: str, before: Optional[dict] = None) -> None:
    """저장한 뒤의 상태를 이력에 남긴다. 이 항목의 이력이 아직 없으면(시드·이전 버전) 고치기 전 상태를 먼저 남겨 되돌릴 수 있게 한다."""
    kind, ref = ("site", row.id) if isinstance(row, SiteProfile) else ("vertical", row.key)
    have = (await db.execute(
        select(SiteProfileRevision.id).where(SiteProfileRevision.kind == kind, SiteProfileRevision.ref == ref).limit(1)
    )).first()
    if have is None and before is not None:
        db.add(SiteProfileRevision(kind=kind, ref=ref, version=row.version - 1, snapshot=before, source="seed", author=None))
    db.add(SiteProfileRevision(kind=kind, ref=ref, version=row.version, snapshot=snapshot_of(row), source=source, author=author))
    await db.flush()
    old = (await db.execute(
        select(SiteProfileRevision.id).where(SiteProfileRevision.kind == kind, SiteProfileRevision.ref == ref)
        .order_by(SiteProfileRevision.version.desc(), SiteProfileRevision.created_at.desc()).offset(MAX_REVISIONS)
    )).scalars().all()
    for rid in old:
        await db.delete(await db.get(SiteProfileRevision, rid))


async def list_revisions(db: AsyncSession, kind: str, ref: str) -> list[SiteProfileRevision]:
    return list((await db.execute(
        select(SiteProfileRevision).where(SiteProfileRevision.kind == kind, SiteProfileRevision.ref == ref)
        .order_by(SiteProfileRevision.version.desc(), SiteProfileRevision.created_at.desc()).limit(MAX_REVISIONS)
    )).scalars().all())


async def _revision(db: AsyncSession, kind: str, ref: str, rev_id: str) -> SiteProfileRevision:
    rev = await db.get(SiteProfileRevision, rev_id)
    if rev is None or rev.kind != kind or rev.ref != ref:
        raise ProfileError(404, "이력을 찾을 수 없습니다")
    return rev


async def restore_site(db: AsyncSession, site_id: str, rev_id: str, author: Optional[str] = None) -> SiteProfile:
    """사이트를 그 이력의 내용으로 되돌린다 (새 버전으로 저장되므로 되돌린 것도 이력에 남는다)."""
    await _site(db, site_id)
    rev = await _revision(db, "site", site_id, rev_id)
    return await save_site(db, {"spec": {}, **rev.snapshot}, site_id=site_id, author=author, source="restore")


async def restore_vertical(db: AsyncSession, key: str, rev_id: str, author: Optional[str] = None) -> SiteVertical:
    await _vertical(db, key)
    rev = await _revision(db, "vertical", key, rev_id)
    return await save_vertical(db, {"spec": {}, **rev.snapshot}, key=key, author=author, source="restore")
