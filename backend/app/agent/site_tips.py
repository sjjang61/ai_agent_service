"""사이트 요령 로더: 분야(vertical) 공통 지침 + 사이트별 요령.

원본은 DB(site_verticals, site_profiles)이고, DB 에서 읽어 온 내용을 메모리 캐시(set_cache)에 둔다. 캐시가 비어 있으면(서버 시작 전, 테스트,
DB 오류) 저장소의 md 파일(app/agent/site_tips/verticals/*.md, sites/*.md. 형식은 그 폴더의 README.md)을 쓴다. 파일은 시드 겸 기본값이다.

시작할 때는 작업에 해당하는 사이트·분야만(start_blocks), 이동할 때는 처음 방문하는 사이트의 것만(jit_text) 골라 쓴다.
브라우저 도구가 동기 코드라 읽기 함수는 모두 동기이고, DB 는 services/site_profile_service.py 가 읽어 캐시에 채운다.
"""
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from app.agent import site_spec

TIPS_DIR = Path(__file__).parent / "site_tips"
_URL = re.compile(r"https?://[^\s)>\]\"']+", re.I)
CHECKLIST_HEADING = "## 분석 체크리스트"
_SPEC_FENCE = re.compile(r"```spec[ \t]*\n(.*?)\n```[ \t]*\n?", re.S)


def _csv(s: Optional[str]) -> tuple[str, ...]:
    return tuple(x.strip().lower() for x in (s or "").split(",") if x.strip())


@dataclass(frozen=True)
class SiteTip:
    name: str
    domains: tuple[str, ...]
    aliases: tuple[str, ...]
    verified: str
    body: str
    vertical: str = ""
    spec: dict = field(default_factory=dict)
    status: str = "verified"  # draft(분석 대기)는 에이전트에게 주지 않는다
    category: str = ""  # 분야가 없는 사이트의 카테고리 key (화면 분류용)
    skills: tuple[str, ...] = ()  # 사이트 분석이 참고할 스킬 이름(소문자)
    commands: tuple = ()  # 분석 전에 돌릴 조회 전용 스킬 명령 [{skill,label,command}]

    def block(self, hint: bool = True, vspec: Optional[dict] = None) -> str:
        head = f"[사이트 요령 · {self.name} · 확인 {self.verified}]"
        tail = "\n(요령과 화면이 다르면 화면을 우선하세요.)" if hint else ""
        if vspec is None:
            v = vertical(self.vertical) if self.vertical else None
            vspec = v.spec if v else None
        parts = [site_spec.render_site(self.spec, vspec), self.body]
        return f"{head}\n" + "\n\n".join(p for p in parts if p) + tail


@dataclass(frozen=True)
class SiteState:
    """사이트 행의 사용 여부만 담은 것 (꺼진 사이트로의 이동을 막는 데 쓴다. 요령은 SiteTip 이 따로 갖는다)."""
    name: str
    domains: tuple[str, ...]
    aliases: tuple[str, ...]
    enabled: bool


@dataclass(frozen=True)
class Vertical:
    key: str
    name: str
    keywords: tuple[str, ...]
    stop_words: tuple[str, ...]
    stop_urls: tuple[str, ...]
    body: str
    checklist: str = ""
    spec: dict = field(default_factory=dict)
    category: str = ""  # 카테고리 key (화면 분류용)
    skills: tuple[str, ...] = ()  # 사이트 분석이 참고할 스킬 이름(소문자)
    confirm_words: tuple[str, ...] = ()  # 승인 후 누를 문구(사용자 작업) / 분석·검증에서는 누르지 않는 문구. '문구@조건' 은 화면에 조건 문구의 요소가 함께 있을 때만

    def block(self) -> str:
        sites = [t.name for t in all_tips() if t.vertical == self.key]
        tail = f"\n요령이 있는 사이트: {', '.join(sites)}" if sites else ""
        parts = [site_spec.render_vertical(self.spec), self.body]
        return f"[분야 지침 · {self.name}]\n" + "\n\n".join(p for p in parts if p) + tail


def _frontmatter(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"---\s*\n(.*?)\n---\s*\n(.*)\Z", raw, re.S)
    if not m:
        raise ValueError(f"{path.name}: 앞머리(--- ... ---)가 없습니다")
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.split(" #")[0].strip()
    return meta, m.group(2).strip()


def split_checklist(body: str) -> tuple[str, str]:
    """분야 md 본문을 (지침, 분석 체크리스트)로 나눈다."""
    head, sep, tail = body.partition(CHECKLIST_HEADING)
    return head.strip(), (tail.strip() if sep else "")


def split_spec(body: str, clean) -> tuple[str, dict]:
    """md 본문에서 ```spec 블록(JSON)을 떼어 (나머지 본문, 정리된 spec)로. 형식이 틀리면 ValueError."""
    m = _SPEC_FENCE.search(body)
    if not m:
        return body.strip(), {}
    try:
        return (body[: m.start()] + body[m.end():]).strip(), clean(json.loads(m.group(1)))
    except (json.JSONDecodeError, site_spec.SpecError) as e:
        raise ValueError(f"spec 블록이 올바르지 않습니다: {e}")


def _commands(raw) -> tuple:
    """md 앞머리 reference_commands(한 줄 JSON)를 읽는다. 형식이 틀리면 ValueError."""
    if not raw:
        return ()
    from app.services.skill_runner import clean_commands

    try:
        return tuple(clean_commands(json.loads(raw)))
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"reference_commands 가 올바르지 않습니다: {e}")


def parse_site_file(path: Path) -> SiteTip:
    meta, body = _frontmatter(path)
    try:
        body, spec = split_spec(body, site_spec.clean_site)
    except ValueError as e:
        raise ValueError(f"{path.name}: {e}")
    return SiteTip(name=meta.get("name", ""), domains=_csv(meta.get("domains")), aliases=_csv(meta.get("aliases")),
                   verified=meta.get("verified", ""), body=body, vertical=meta.get("vertical", "").strip().lower(), spec=spec,
                   status=meta.get("status", "verified").strip().lower() or "verified", category=meta.get("category", "").strip().lower(), skills=_csv(meta.get("skills")),
                   commands=_commands(meta.get("reference_commands")))


def parse_vertical_file(path: Path) -> Vertical:
    meta, body = _frontmatter(path)
    try:
        body, spec = split_spec(body, site_spec.clean_vertical)
    except ValueError as e:
        raise ValueError(f"{path.name}: {e}")
    guide, checklist = split_checklist(body)
    return Vertical(key=meta.get("key", "").strip().lower(), name=meta.get("name", ""), keywords=_csv(meta.get("keywords")),
                    stop_words=_csv(meta.get("stop_words")), stop_urls=_csv(meta.get("stop_urls")), body=guide, checklist=checklist, spec=spec,
                    category=meta.get("category", "").strip().lower(), skills=_csv(meta.get("skills")), confirm_words=_csv(meta.get("confirm_words")))


@lru_cache(maxsize=1)
def file_tips() -> tuple[SiteTip, ...]:
    return tuple(parse_site_file(p) for p in sorted((TIPS_DIR / "sites").glob("*.md")))


@lru_cache(maxsize=1)
def file_verticals() -> tuple[Vertical, ...]:
    return tuple(parse_vertical_file(p) for p in sorted((TIPS_DIR / "verticals").glob("*.md")))


# DB 에서 읽어 온 내용. None 이면 파일을 쓴다.
_cache: Optional[tuple[tuple[Vertical, ...], tuple[SiteTip, ...]]] = None
_common: Optional[str] = None  # DB 의 전체 공통 지침. None 이면 파일을 쓴다
_states: tuple[SiteState, ...] = ()  # DB 의 모든 사이트 행의 사용 여부 (캐시와 함께 채운다)


def set_cache(verticals, tips, states=(), common: Optional[str] = None) -> None:
    global _cache, _states, _common
    _cache = (tuple(verticals), tuple(tips))
    _states = tuple(states)
    _common = common


def clear_cache() -> None:
    global _cache, _states, _common
    _cache, _states, _common = None, (), None


def file_common() -> str:
    """저장소 md(common.md)의 전체 공통 지침 본문."""
    path = TIPS_DIR / "common.md"
    return _frontmatter(path)[1] if path.exists() else ""


def common_text() -> str:
    """모든 브라우저 작업·분석에 붙는 전체 공통 지침. DB 에서 읽은 것이 있으면 그것을(비워 두면 없음), 없으면 md 파일을 쓴다."""
    return (file_common() if _common is None else _common).strip()


def all_tips() -> tuple[SiteTip, ...]:
    return _cache[1] if _cache is not None else tuple(t for t in file_tips() if t.status != "draft")


def all_verticals() -> tuple[Vertical, ...]:
    return _cache[0] if _cache is not None else file_verticals()


def vertical(key: str) -> Optional[Vertical]:
    key = (key or "").strip().lower()
    return next((v for v in all_verticals() if v.key == key), None)


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def _host_matches(host: str, domain: str) -> bool:
    return bool(host) and (host == domain or host.endswith("." + domain))


def tips_for_url(url: str) -> list[SiteTip]:
    """이 주소의 사이트 요령들 (하위 도메인 포함). 가장 구체적인 도메인이 이긴다 (flight.naver.com 이 naver.com 보다 먼저).
    한 사이트가 여러 분야를 가지면(아고다 · 항공권/호텔) 같은 도메인의 요령이 여럿 나온다. 없으면 빈 목록."""
    host = _host(url)
    best_len, out = 0, []
    for t in all_tips():
        n = max((len(d) for d in t.domains if _host_matches(host, d)), default=0)
        if n > best_len:
            best_len, out = n, [t]
        elif n and n == best_len:
            out.append(t)
    return out


def _path_head(url: str) -> str:
    return (urlparse(url).path.strip("/").split("/")[0] if url else "").lower()


def _spec_urls(t: SiteTip) -> list[str]:
    s = t.spec or {}
    return [x.get("url", "") for k in ("entry", "menus", "flow") for x in s.get(k, [])]


def _scoped(t: SiteTip) -> bool:
    """진입 주소가 모두 도메인의 특정 경로(/travel/flights 등)에 있는 요령 (같은 도메인의 일반 요령과 구분하려는 것: google.com 의 검색엔진 vs Google Flights)."""
    entries = [x.get("url", "") for x in (t.spec or {}).get("entry", [])]
    return bool(entries) and all(_path_head(u) for u in entries)


def pick(url: str, shown: Optional[set] = None) -> list[SiteTip]:
    """주소에 해당하는 요령 중 지금 쓸 것. 같은 도메인에 분야가 다른 요령이 여럿이면
    (1) 주소의 첫 경로(/flights, /hotels)가 그 요령의 진입·메뉴·단계 주소와 같은 것, (2) 이미 안내한 분야의 것, 순으로 좁히고, 그래도 못 정하면 모두 준다.
    경로를 먼저 보는 이유: 호텔로 시작한 작업이 같은 사이트의 항공권 화면으로 이동하면 그 화면의 요령을 줘야 하기 때문이다."""
    cands = tips_for_url(url)
    if len(cands) <= 1:
        return cands
    head = _path_head(url)
    by_path = [t for t in cands if head and any(_path_head(u) == head for u in _spec_urls(t))]
    if by_path:
        return by_path
    plain = [t for t in cands if not _scoped(t)]
    if plain and len(plain) < len(cands):  # 경로가 맞는 요령이 없으면, 경로 전용 요령(Google Flights)은 빼고 일반 요령(검색엔진)만
        return plain
    seen = {s[1:] for s in (shown or ()) if isinstance(s, str) and s.startswith("@")}
    return [t for t in cands if t.vertical in seen] or cands


def for_url(url: str, prefer: Optional[set] = None) -> SiteTip | None:
    """이 주소의 사이트 요령 하나 (분야가 여럿이면 prefer 분야 키가 있는 것을 먼저). 없으면 None."""
    cands = tips_for_url(url)
    return next((t for t in cands if prefer and t.vertical in prefer), cands[0] if cands else None)


def match_task(task: str, start_url: str | None = None) -> list[SiteTip]:
    """작업에 해당하는 사이트 요령: 시작 URL·작업 문장 속 주소의 도메인, 또는 사이트 이름(aliases)이 나오는 것.
    같은 도메인에 분야가 다른 요령이 여럿이면(아고다 · 항공권/호텔) 작업 문장의 분야 키워드로 좁히고, 키워드가 없으면 모두 준다."""
    text = (task or "").lower()
    hosts = {_host(u) for u in _URL.findall(text)} | ({_host(start_url)} if start_url else set())
    out = []
    for t in all_tips():
        if any(_host_matches(h, d) for h in hosts for d in t.domains) or any(d in text for d in t.domains) or any(a in text for a in t.aliases):
            out.append(t)
    wanted = {v.key for v in all_verticals() if any(k in text for k in v.keywords)}
    narrowed = []
    for t in out:
        group = [o for o in out if o is not t and set(o.domains) & set(t.domains)]
        in_group = [o for o in group + [t] if o.vertical in wanted]
        alias_hit = any(a in text for a in t.aliases)
        if group and _scoped(t) and not alias_hit and t.vertical not in wanted and any(not _scoped(o) for o in group):
            continue  # 같은 도메인의 일반 요령(검색엔진)이 있으면, 경로 전용 요령은 이름·분야 키워드를 말했을 때만
        narrowed.append(t) if (not group or not in_group or t.vertical in wanted) else None
    return narrowed


def match_verticals(task: str, tips: Optional[list] = None) -> list[Vertical]:
    """작업에 해당하는 분야: 해당 사이트의 분야, 또는 작업 문장에 분야 키워드가 나오는 것."""
    text = (task or "").lower()
    keys = {t.vertical for t in (tips or []) if t.vertical}
    return [v for v in all_verticals() if v.key in keys or any(k in text for k in v.keywords)]


def blocked(url: str) -> Optional[str]:
    """이 주소가 '사용 안 함'으로 꺼진 사이트면 에이전트에게 돌려줄 사유, 아니면 None.
    가장 구체적인 도메인의 행들이 모두 꺼져 있을 때만 막는다 (같은 도메인의 다른 분야 행이 켜져 있으면 막지 않는다)."""
    host = _host(url)
    best_len, group = 0, []
    for s in _states:
        n = max((len(d) for d in s.domains if _host_matches(host, d)), default=0)
        if n > best_len:
            best_len, group = n, [s]
        elif n and n == best_len:
            group.append(s)
    if group and all(not s.enabled for s in group):
        return (f"사이트 설정에서 사용 안 함으로 꺼진 사이트라 접속하지 않았습니다: {group[0].name} ({host}). "
                "이 사이트를 다시 열지 말고 다른 사이트나 방법으로 진행하세요. 마땅한 대안이 없으면 이 사이트를 쓸 수 없어 제외했다고 사용자에게 알리세요.")
    return None


def disabled_blocks(task: str, start_url: str | None = None) -> list[str]:
    """작업이 '사용 안 함' 사이트를 가리키면(이름·도메인) 시작 지침에 붙일 안내. 헛되이 접속을 시도하지 않게 한다."""
    text = (task or "").lower()
    hosts = {_host(u) for u in _URL.findall(text)} | ({_host(start_url)} if start_url else set())
    names = []
    for s in _states:
        if s.enabled:
            continue
        if any(_host_matches(h, d) for h in hosts for d in s.domains) or any(d in text for d in s.domains) or any(a in text for a in s.aliases):
            if blocked(f"https://{s.domains[0]}/") and s.name not in names:  # 같은 도메인의 켜진 행이 있으면 안내하지 않는다
                names.append(s.name)
    if not names:
        return []
    return ["[사용 안 함 사이트] " + ", ".join(names) + " — 사이트 설정에서 꺼져 있어 접속할 수 없습니다. 이 사이트는 건너뛰고 다른 사이트로 진행하거나, 대안이 없으면 사용자에게 쓸 수 없다고 알리세요."]


def start_blocks(task: str, start_url: str | None = None) -> tuple[list[str], set[str]]:
    """시작 지침에 붙일 블록(분야 지침 먼저, 사이트 요령 다음)과, 이미 안내한 것의 표시(사이트 이름, '@분야키')."""
    tips = match_task(task, start_url)
    verticals = match_verticals(task, tips)
    common = common_text()
    blocks = ([f"[전체 공통 지침]\n{common}"] if common else []) + disabled_blocks(task, start_url) + [v.block() for v in verticals] + [t.block(hint=False) for t in tips]
    return blocks, {t.name for t in tips} | {f"@{v.key}" for v in verticals}


def jit_text(url: str, shown: set) -> str:
    """처음 방문하는 사이트의 요령(와 아직 안내하지 않은 분야 지침). 이미 안내했거나 없으면 빈 문자열. shown 에 안내한 것을 기록한다."""
    parts = []
    for tip in pick(url, shown):
        if tip.name in shown:
            continue
        shown.add(tip.name)
        v = vertical(tip.vertical) if tip.vertical else None
        if v is not None and f"@{v.key}" not in shown:
            shown.add(f"@{v.key}")
            parts.append(v.block())
        parts.append(tip.block())
    return "\n\n".join(parts)


def confirm_rules(url: str, shown: set) -> tuple[str, ...]:
    """지금 작업에 적용되는 분야의 '승인 후 누를 문구'(사용자 작업은 매번 승인, 분석·검증은 누르지 않음). stop_rules 와 같은 방식으로 분야를 고른다."""
    keys = {s[1:] for s in shown if isinstance(s, str) and s.startswith("@")}
    keys |= {t.vertical for t in tips_for_url(url) if t.vertical} if url else set()
    words: list[str] = []
    for v in all_verticals():
        if v.key in keys:
            words += v.confirm_words
    return tuple(dict.fromkeys(words))


def stop_rules(url: str, shown: set) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """지금 작업에 적용되는 분야의 '누르지 않을 라벨'과 '이동하지 않을 주소 문구'. shown 은 안내한 분야('@키') 표시.
    막는 규칙이라 같은 도메인의 모든 분야 것을 적용한다 (어느 분야인지 못 정해도 안전한 쪽)."""
    keys = {s[1:] for s in shown if isinstance(s, str) and s.startswith("@")}
    keys |= {t.vertical for t in tips_for_url(url) if t.vertical} if url else set()
    words: list[str] = []
    urls: list[str] = []
    for v in all_verticals():
        if v.key in keys:
            words += v.stop_words
            urls += v.stop_urls
    return tuple(dict.fromkeys(words)), tuple(dict.fromkeys(urls))
