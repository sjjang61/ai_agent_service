"""사이트별 요령 로더. 요령 본문은 app/agent/site_tips/*.md (형식은 그 폴더의 README.md) 에 있다.

시작할 때는 작업에 해당하는 사이트만(match_task), 이동할 때는 처음 방문하는 도메인의 것만(for_url) 골라 쓴다.
"""
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

TIPS_DIR = Path(__file__).parent / "site_tips"
_URL = re.compile(r"https?://[^\s)>\]\"']+", re.I)


@dataclass(frozen=True)
class SiteTip:
    name: str
    domains: tuple[str, ...]
    aliases: tuple[str, ...]
    verified: str
    body: str

    def block(self, hint: bool = True) -> str:
        head = f"[사이트 요령 · {self.name} · 확인 {self.verified}]"
        tail = "\n(요령과 화면이 다르면 화면을 우선하세요.)" if hint else ""
        return f"{head}\n{self.body}{tail}"


def _parse(path: Path) -> SiteTip:
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"---\s*\n(.*?)\n---\s*\n(.*)\Z", raw, re.S)
    if not m:
        raise ValueError(f"{path.name}: 앞머리(--- ... ---)가 없습니다")
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.split(" #")[0].strip()
    split = lambda s: tuple(x.strip().lower() for x in (s or "").split(",") if x.strip())
    return SiteTip(name=meta.get("name", ""), domains=split(meta.get("domains")), aliases=split(meta.get("aliases")),
                   verified=meta.get("verified", ""), body=m.group(2).strip())


@lru_cache(maxsize=1)
def all_tips() -> tuple[SiteTip, ...]:
    return tuple(_parse(p) for p in sorted(TIPS_DIR.glob("*.md")) if p.name != "README.md")


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def _host_matches(host: str, domain: str) -> bool:
    return bool(host) and (host == domain or host.endswith("." + domain))


def for_url(url: str) -> SiteTip | None:
    """이 주소의 사이트 요령 (하위 도메인 포함). 없으면 None."""
    host = _host(url)
    for t in all_tips():
        if any(_host_matches(host, d) for d in t.domains):
            return t
    return None


def match_task(task: str, start_url: str | None = None) -> list[SiteTip]:
    """작업에 해당하는 사이트 요령: 시작 URL·작업 문장 속 주소의 도메인, 또는 사이트 이름(aliases)이 나오는 것."""
    text = (task or "").lower()
    hosts = {_host(u) for u in _URL.findall(text)} | ({_host(start_url)} if start_url else set())
    out = []
    for t in all_tips():
        if any(_host_matches(h, d) for h in hosts for d in t.domains) or any(d in text for d in t.domains) or any(a in text for a in t.aliases):
            out.append(t)
    return out
