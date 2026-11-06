"""가격 정책 페이지에서 모델 단가를 읽어 DB 에 갱신한다.

OpenAI 가격 페이지(developers.openai.com)는 Astro 로 만들어져 가격표 데이터가 <astro-island props="..."> 안에 JSON 으로 들어 있다.
1) 그 구조화 데이터(가장 정확), 2) HTML 표, 3) 페이지 텍스트를 LLM 으로 추출 — 순서로 시도한다.
Standard(일반) 요금만 사용한다. 사용자가 입력한 URL 을 서버가 가져오므로 사설 주소·내부망은 막는다(SSRF 방지).
"""
import html as htmllib
import ipaddress
import json
import logging
import re
import socket
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import render
from app.models.model_price import AppSetting, ModelPrice
from app.services import pricing

logger = logging.getLogger(__name__)

DEFAULT_PRICING_URL = "https://developers.openai.com/api/docs/pricing?utm_source=chatgpt.com&latest-pricing-expanded=true"
MAX_PAGE_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 3
FETCH_TIMEOUT_SECONDS = 20
MIN_MODELS = 3
LLM_TEXT_CHARS = 60000

K_URL, K_AT, K_STATUS, K_METHOD, K_COUNT = "pricing.url", "pricing.last_updated_at", "pricing.last_status", "pricing.last_method", "pricing.last_count"
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._:\-]{1,80}$")


class PricingError(ValueError):
    """가격 갱신 실패 (메시지는 사용자에게 그대로 보인다)."""


# ── URL 검사 (SSRF 방지) ─────────────────────────────────────────────────────
def validate_public_url(url: str) -> str:
    u = (url or "").strip()
    if len(u) > 1000:
        raise PricingError("URL 이 너무 깁니다")
    p = urlparse(u)
    if p.scheme != "https" or not p.hostname:
        raise PricingError("https:// 로 시작하는 주소만 사용할 수 있습니다")
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or 443, proto=socket.IPPROTO_TCP)
    except OSError as e:
        raise PricingError(f"주소를 찾을 수 없습니다: {p.hostname}") from e
    if not infos or any(not ipaddress.ip_address(i[4][0]).is_global for i in infos):
        raise PricingError("내부망·사설 주소는 사용할 수 없습니다")
    return u


async def fetch_page(url: str) -> str:
    """페이지 HTML 을 가져온다 (https·공인 주소만, 리다이렉트도 같은 검사, 크기 제한)."""
    current = validate_public_url(url)
    async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=False,
                                 headers={"User-Agent": "Mozilla/5.0 (compatible; agent-pricing-update)"}) as client:
        for _ in range(MAX_REDIRECTS + 1):
            async with client.stream("GET", current) as resp:
                if resp.status_code in (301, 302, 303, 307, 308) and resp.headers.get("location"):
                    current = validate_public_url(urljoin(current, resp.headers["location"]))
                    continue
                if resp.status_code != 200:
                    raise PricingError(f"페이지를 가져오지 못했습니다 (HTTP {resp.status_code})")
                buf = bytearray()
                async for chunk in resp.aiter_bytes():
                    buf.extend(chunk)
                    if len(buf) > MAX_PAGE_BYTES:
                        raise PricingError("페이지가 너무 큽니다 (5MB 초과)")
                return bytes(buf).decode(resp.encoding or "utf-8", errors="replace")
    raise PricingError("리다이렉트가 너무 많습니다")


# ── 파서 ─────────────────────────────────────────────────────────────────────
def _num(v) -> Optional[float]:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        m = re.search(r"-?\d+(?:,\d{3})*(?:\.\d+)?", v.replace("$", ""))
        if m and v.strip() not in ("-", "—", ""):
            return float(m.group().replace(",", ""))
    return None


def _clean_name(name) -> Optional[str]:
    n = re.sub(r"\s*\(.*?\)\s*", " ", str(name or "")).strip().lower()
    return n if _NAME_RE.match(n) else None


def _valid(i, o) -> bool:
    return i is not None and o is not None and 0 <= i <= 1000 and 0 <= o <= 2000


def _decode_astro(v):
    """Astro 직렬화([0, 값] / [1, 배열])를 일반 JSON 값으로."""
    if isinstance(v, list) and len(v) == 2 and v[0] in (0, 1):
        t, x = v
        if t == 0:
            return {k: _decode_astro(y) for k, y in x.items()} if isinstance(x, dict) else x
        return [_decode_astro(y) for y in x]
    if isinstance(v, dict):
        return {k: _decode_astro(y) for k, y in v.items()}
    return v


def parse_islands(page: str) -> dict:
    """구조화 데이터: tier=standard 텍스트 모델 행과 첫 이미지 모델 그룹."""
    out: dict = {}
    image_done = False
    for attrs in re.findall(r"<astro-island\b([^>]*)>", page):
        m = re.search(r'props="([^"]*)"', attrs)
        if not m:
            continue
        try:
            props = _decode_astro(json.loads(htmllib.unescape(m.group(1))))
        except ValueError:
            continue
        if not isinstance(props, dict):
            continue
        if props.get("tier") == "standard" and isinstance(props.get("rows"), list):
            for row in props["rows"]:
                if not isinstance(row, list) or len(row) < 4:
                    continue
                name = _clean_name(row[0])
                inp, cached = _num(row[1]), _num(row[2])
                outp = _num(row[4]) if len(row) >= 5 else _num(row[3])  # 최신 모델은 캐시 쓰기 열이 하나 더 있다
                if name and _valid(inp, outp):
                    out.setdefault(name, (inp, cached, outp))
        elif isinstance(props.get("groups"), list) and not image_done and any("image" in str((g or {}).get("model", "")).lower() for g in props["groups"] if isinstance(g, dict)):
            # 이미지 모델: 첫 번째 표가 Standard. (텍스트 입력, 텍스트 캐시 입력, 이미지 출력)
            for g in props["groups"]:
                name = _clean_name(g.get("model") if isinstance(g, dict) else None)
                rows = {str(r[0]).lower(): r for r in (g.get("rows") or []) if isinstance(r, list) and len(r) >= 4}
                img, txt = rows.get("image"), rows.get("text")
                inp = _num(txt[1]) if txt else (_num(img[1]) if img else None)
                cached = _num(txt[3]) if txt else (_num(img[3]) if img else None)
                outp = _num(img[2]) if img else None
                if name and _valid(inp, outp):
                    out.setdefault(name, (inp, cached, outp))
            image_done = True
    return out


class _Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables: list = []
        self._cur = self._row = self._cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._cur = []
        elif tag == "tr" and self._cur is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self._cur.append(self._row)
            self._row = None
        elif tag == "table" and self._cur is not None:
            self.tables.append(self._cur)
            self._cur = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def parse_tables(page: str) -> dict:
    """HTML 표: 'Model / Input / Output (/ Cached input)' 머리글이 있는 표에서 모델별 첫 번째 값을 쓴다."""
    p = _Tables()
    p.feed(page)
    out: dict = {}
    for t in p.tables:
        head_i = next((i for i, r in enumerate(t[:3]) if {"input", "output"} <= {c.lower() for c in r} and any(c.lower().startswith("model") for c in r)), None)
        if head_i is None:
            continue
        head = [c.lower() for c in t[head_i]]
        ci = {k: next((j for j, c in enumerate(head) if c == k), None) for k in ("input", "output", "cached input")}
        mi = next(j for j, c in enumerate(head) if c.startswith("model"))
        for r in t[head_i + 1:]:
            if len(r) <= max(j for j in (mi, ci["input"], ci["output"]) if j is not None):
                continue
            name = _clean_name(r[mi])
            inp, outp = _num(r[ci["input"]]), _num(r[ci["output"]])
            cached = _num(r[ci["cached input"]]) if ci["cached input"] is not None and ci["cached input"] < len(r) else None
            if name and _valid(inp, outp):
                out.setdefault(name, (inp, cached, outp))
    return out


def page_text(page: str) -> str:
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", page)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    return " ".join(htmllib.unescape(t).split())


async def parse_with_llm(page: str) -> dict:
    from app.agent.react_agent import AgentRunner
    from app.services.memory_extractor import _content_text

    prompt = render("pricing_extract", text=page_text(page)[:LLM_TEXT_CHARS])
    raw = _content_text((await AgentRunner(tools=[]).llm.ainvoke(prompt)).content)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {}
    out: dict = {}
    for it in (json.loads(m.group()).get("prices") or []):
        name, inp, outp, cached = _clean_name(it.get("model")), _num(it.get("input")), _num(it.get("output")), _num(it.get("cached_input"))
        if name and _valid(inp, outp):
            out.setdefault(name, (inp, cached, outp))
    return out


async def parse_pricing(page: str) -> tuple[dict, str]:
    """(모델 → (입력, 캐시 입력, 출력), 사용한 방법). 모두 실패하면 PricingError."""
    for method, fn in (("structured", parse_islands), ("table", parse_tables)):
        prices = fn(page)
        if len(prices) >= MIN_MODELS:
            return prices, method
    try:
        prices = await parse_with_llm(page)
    except Exception as e:  # noqa: BLE001
        logger.warning("[pricing] LLM 추출 실패: %s", e)
        prices = {}
    if len(prices) >= MIN_MODELS:
        return prices, "llm"
    raise PricingError("가격표를 읽지 못했습니다. 페이지 형식이 바뀌었거나 모델 가격 표가 없는 페이지일 수 있습니다.")


# ── 설정·갱신 ────────────────────────────────────────────────────────────────
async def _get(db: AsyncSession, key: str) -> Optional[str]:
    row = (await db.execute(select(AppSetting).where(AppSetting.key == key))).scalar_one_or_none()
    return row.value if row else None


async def _put(db: AsyncSession, key: str, value: Optional[str]) -> None:
    row = (await db.execute(select(AppSetting).where(AppSetting.key == key))).scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=key, value=value))


async def get_state(db: AsyncSession) -> dict:
    return {
        "url": await _get(db, K_URL) or DEFAULT_PRICING_URL,
        "default_url": DEFAULT_PRICING_URL,
        "last_updated_at": await _get(db, K_AT),
        "last_status": await _get(db, K_STATUS),
        "last_method": await _get(db, K_METHOD),
        "last_count": int(await _get(db, K_COUNT) or 0),
    }


async def set_url(db: AsyncSession, url: str) -> str:
    u = validate_public_url(url)
    await _put(db, K_URL, u)
    await db.commit()
    return u


async def refresh(db: AsyncSession, url: Optional[str] = None) -> dict:
    """URL 의 가격 페이지를 가져와 단가를 갱신한다. 실패하면 기존 단가는 그대로 두고 PricingError."""
    u = url or (await _get(db, K_URL)) or DEFAULT_PRICING_URL
    try:
        prices, method = await parse_pricing(await fetch_page(u))
    except PricingError as e:
        await _put(db, K_STATUS, f"오류: {e}")
        await db.commit()
        raise
    before = {**pricing.PRICES, **pricing._db_prices}
    existing = {r.model: r for r in (await db.execute(select(ModelPrice))).scalars().all()}
    added, changed = [], []
    for name, (inp, cached, outp) in prices.items():
        old = before.get(name)
        if old is None:
            added.append(name)
        elif tuple(old) != (inp, cached, outp):
            changed.append({"model": name, "old": {"input": old[0], "output": old[2]}, "new": {"input": inp, "output": outp}})
        row = existing.get(name)
        if row:
            row.input_price, row.cached_input_price, row.output_price, row.source_url = inp, cached, outp, u
        else:
            db.add(ModelPrice(model=name, input_price=inp, cached_input_price=cached, output_price=outp, source_url=u))
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    await _put(db, K_URL, u)
    await _put(db, K_AT, now)
    await _put(db, K_STATUS, "성공")
    await _put(db, K_METHOD, method)
    await _put(db, K_COUNT, str(len(prices)))
    await db.commit()
    await pricing.load_db_prices(db)
    return {"method": method, "model_count": len(prices), "added": sorted(added), "changed": changed, "updated_at": now}
