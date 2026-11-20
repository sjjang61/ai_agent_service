"""웹사이트 분석의 구조화 데이터: 분야의 입력값·표준 플로우, 사이트의 진입 주소·메뉴 지도·입력 방법·단계별 동작.

분야(vertical.spec)   : {inputs: [{key, label, required, format, example}], flow: [{key, title, desc, write}], sample: {입력키: 샘플값}}
사이트(site.spec)      : {entry: [{label, url}], menus: [{name, path, url}], inputs: {입력키: {how, param}},
                          flow: [{key, how, url}], stop_point}

clean_* 는 사용자·에이전트가 보낸 값을 검증·정리하고(잘못되면 SpecError), render_* 는 브라우저 에이전트에게 줄 텍스트로 푼다.
이 모듈은 DB·네트워크를 모른다 (site_tips 와 서비스가 쓴다).
"""
import re
from typing import Optional

KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,29}$")
MAX_INPUTS, MAX_FLOW, MAX_ENTRY, MAX_MENUS = 20, 15, 10, 30


class SpecError(ValueError):
    pass


def _s(v, n: int) -> str:
    return str(v if v is not None else "").strip()[:n]


def _list(raw, name: str, limit: int) -> list:
    if raw in (None, ""):
        return []
    if not isinstance(raw, list):
        raise SpecError(f"{name} 는 목록이어야 합니다")
    if len(raw) > limit:
        raise SpecError(f"{name} 는 최대 {limit}개까지입니다")
    return [x for x in raw if isinstance(x, dict)]


def _key(raw, what: str) -> str:
    key = _s(raw, 30).lower()
    if not KEY_RE.match(key):
        raise SpecError(f"{what} 키가 올바르지 않습니다: '{key}' (영문 소문자로 시작하는 영문 소문자·숫자·밑줄)")
    return key


def _url(raw, what: str) -> str:
    url = _s(raw, 500)
    if url and not re.match(r"^https?://[^\s]+$", url, re.I):
        raise SpecError(f"{what} 주소는 http(s):// 로 시작해야 합니다: {url[:60]}")
    return url


def clean_vertical(raw) -> dict:
    """분야 spec 정리. 비어 있으면 {}."""
    if not raw:
        return {}
    if not isinstance(raw, dict):
        raise SpecError("spec 은 객체여야 합니다")
    inputs, seen = [], set()
    for it in _list(raw.get("inputs"), "입력값", MAX_INPUTS):
        if not _s(it.get("key"), 30) and not _s(it.get("label"), 60):
            continue  # 빈 행
        key = _key(it.get("key"), "입력값")
        if key in seen:
            raise SpecError(f"입력값 키가 겹칩니다: {key}")
        seen.add(key)
        inputs.append({"key": key, "label": _s(it.get("label"), 60) or key, "required": bool(it.get("required", True)),
                       "format": _s(it.get("format"), 200), "example": _s(it.get("example"), 100)})
    flow, seen_f = [], set()
    for it in _list(raw.get("flow"), "플로우", MAX_FLOW):
        if not _s(it.get("key"), 30) and not _s(it.get("title"), 60):
            continue
        key = _key(it.get("key"), "단계")
        if key in seen_f:
            raise SpecError(f"단계 키가 겹칩니다: {key}")
        seen_f.add(key)
        flow.append({"key": key, "title": _s(it.get("title"), 60) or key, "desc": _s(it.get("desc"), 400), "write": bool(it.get("write", False))})
    sample_raw = raw.get("sample") if isinstance(raw.get("sample"), dict) else {}
    sample = {k: _s(v, 100) for k, v in sample_raw.items() if k in seen and _s(v, 100)}  # 정의된 입력값에 대한 것만
    out = {"inputs": inputs, "flow": flow, "sample": sample}
    return out if (inputs or flow) else {}


def clean_site(raw) -> dict:
    """사이트 spec 정리. 비어 있으면 {}."""
    if not raw:
        return {}
    if not isinstance(raw, dict):
        raise SpecError("spec 은 객체여야 합니다")
    entry = []
    for it in _list(raw.get("entry"), "진입 주소", MAX_ENTRY):
        url = _url(it.get("url"), "진입")
        if url:
            entry.append({"label": _s(it.get("label"), 60), "url": url})
    menus = []
    for it in _list(raw.get("menus"), "메뉴", MAX_MENUS):
        name = _s(it.get("name"), 60)
        if name:
            menus.append({"name": name, "path": _s(it.get("path"), 200), "url": _url(it.get("url"), "메뉴")})
    inputs: dict = {}
    raw_inputs = raw.get("inputs") if isinstance(raw.get("inputs"), dict) else {}
    if len(raw_inputs) > MAX_INPUTS:
        raise SpecError(f"입력 방법은 최대 {MAX_INPUTS}개까지입니다")
    for k, v in raw_inputs.items():
        v = v if isinstance(v, dict) else {"how": v}
        how, param = _s(v.get("how"), 500), _s(v.get("param"), 100)
        if how or param:
            inputs[_key(k, "입력 방법")] = {"how": how, "param": param}
    flow, seen = [], set()
    for it in _list(raw.get("flow"), "단계별 동작", MAX_FLOW):
        how, url = _s(it.get("how"), 600), _url(it.get("url"), "단계")
        if not how and not url:
            continue
        key = _key(it.get("key"), "단계")
        if key in seen:
            raise SpecError(f"단계 키가 겹칩니다: {key}")
        seen.add(key)
        flow.append({"key": key, "how": how, "url": url})
    stop = _s(raw.get("stop_point"), 300)
    out = {"entry": entry, "menus": menus, "inputs": inputs, "flow": flow, "stop_point": stop}
    return out if (entry or menus or inputs or flow or stop) else {}


# ── 에이전트에게 줄 텍스트 ─────────────────────────────────────
def render_vertical(spec: Optional[dict]) -> str:
    if not spec:
        return ""
    lines: list[str] = []
    if spec.get("inputs"):
        lines.append("입력값 (필수 값을 사용자가 말하지 않았고 결과가 달라진다면 추측하지 말고 확인하세요):")
        for i in spec["inputs"]:
            extra = " · ".join(x for x in (i.get("format"), f"예: {i['example']}" if i.get("example") else "") if x)
            lines.append(f"- {i['label']} ({i['key']}, {'필수' if i.get('required') else '선택'})" + (f" — {extra}" if extra else ""))
    if spec.get("flow"):
        lines.append("표준 진행 단계:")
        for n, s in enumerate(spec["flow"], 1):
            mark = " [상태를 바꾸는 단계: 사용자가 요청했을 때만]" if s.get("write") else ""
            lines.append(f"{n}. {s['title']}{mark}" + (f" — {s['desc']}" if s.get("desc") else ""))
    return "\n".join(lines)


def render_site(spec: Optional[dict], vspec: Optional[dict] = None) -> str:
    if not spec:
        return ""
    labels = {i["key"]: i["label"] for i in (vspec or {}).get("inputs", [])}
    titles = {s["key"]: s["title"] for s in (vspec or {}).get("flow", [])}
    lines: list[str] = []
    if spec.get("entry"):
        lines.append("진입·직접 이동 주소 ({키} 는 입력값으로 바꿉니다):")
        lines += [f"- {e['label'] + ': ' if e.get('label') else ''}{e['url']}" for e in spec["entry"]]
    if spec.get("menus"):
        lines.append("메뉴·화면 지도:")
        for m in spec["menus"]:
            where = f" — {m['path']}" if m.get("path") else ""
            lines.append(f"- {m['name']}{where}" + (f" ({m['url']})" if m.get("url") else ""))
    if spec.get("inputs"):
        lines.append("입력값을 넣는 방법:")
        for k, v in spec["inputs"].items():
            param = f" [주소 파라미터: {v['param']}]" if v.get("param") else ""
            lines.append(f"- {labels.get(k, k)}: {v.get('how', '')}{param}".rstrip())
    if spec.get("flow"):
        order = [s["key"] for s in (vspec or {}).get("flow", [])]
        items = sorted(spec["flow"], key=lambda s: order.index(s["key"]) if s["key"] in order else len(order))
        lines.append("단계별 이 사이트에서의 동작:")
        for n, s in enumerate(items, 1):
            lines.append(f"{n}. {titles.get(s['key'], s['key'])}: {s.get('how', '')}" + (f" ({s['url']})" if s.get("url") else ""))
    if spec.get("stop_point"):
        lines.append(f"멈출 지점: {spec['stop_point']}")
    return "\n".join(lines)


def sample_text(vspec: Optional[dict], override: Optional[dict] = None) -> str:
    """재현 검증에 쓸 샘플 입력값을 '라벨: 값' 줄로. 분야에 정의된 입력값만, override 가 샘플보다 우선한다."""
    if not vspec:
        return ""
    values = {**(vspec.get("sample") or {}), **{k: v for k, v in (override or {}).items() if str(v).strip()}}
    return "\n".join(f"- {i['label']} ({i['key']}): {values[i['key']]}" for i in vspec.get("inputs", []) if values.get(i["key"]))
