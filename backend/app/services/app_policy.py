"""웹앱 공개 정책: 호스트명 slug, 공개 URL, 등록 전 자동 점검(비밀 탐지), 검수 결정, 요청률 제한."""
import gzip
import re
import tarfile
import time
from collections import defaultdict, deque
from typing import Optional

from app.config import settings

CATEGORIES = ["productivity", "dev-tools", "data", "design", "education", "entertainment", "game", "business", "other"]
MAX_SCAN_FILE = 1_000_000
MAX_SCAN_TOTAL = 30_000_000

_SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----"), "개인 키"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"), "API 키(sk-…)"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS 액세스 키"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"), "GitHub 토큰"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"), "Slack 토큰"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}"), "Google API 키"),
]
_SECRET_NAMES = re.compile(r"(^|/)(\.env(\..*)?|id_rsa|id_ed25519|.*\.pem|.*\.p12|\.npmrc|\.netrc|credentials(\.json)?)$", re.I)


def make_slug(name: str, app_id: str) -> str:
    """공개 호스트명 라벨: 이름의 영숫자·하이픈 + 앱 id 앞 6자 (이름이 한글뿐이면 'app')."""
    base = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:40].strip("-") or "app"
    return f"{base}-{app_id.replace('-', '')[:6]}"


def public_url(slug: str) -> str:
    port = settings.APP_PUBLIC_PORT
    default = (settings.APP_PUBLIC_SCHEME == "http" and port == 80) or (settings.APP_PUBLIC_SCHEME == "https" and port == 443)
    return f"{settings.APP_PUBLIC_SCHEME}://{slug}.{settings.APP_PUBLIC_DOMAIN}{'' if default else f':{port}'}/"


def host_slug(host_header: Optional[str]) -> Optional[str]:
    """Host 헤더 'slug.도메인[:포트]' 에서 slug. 도메인이 다르거나 단계가 더 깊으면 None."""
    host = (host_header or "").split(":")[0].lower().rstrip(".")
    suffix = "." + settings.APP_PUBLIC_DOMAIN.lower()
    if not host.endswith(suffix):
        return None
    label = host[: -len(suffix)]
    return label if label and "." not in label and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,69}", label) else None


def scan_artifact(path_gz: str) -> list:
    """공개 전 점검: 비밀 파일 이름, 코드·설정 안의 키/토큰 패턴. 문제 목록(빈 목록이면 통과). node_modules·큰 파일은 건너뛴다."""
    issues: list = []
    total = 0
    with gzip.open(path_gz) as g, tarfile.open(fileobj=g) as tar:
        for m in tar:
            if not m.isfile() or "node_modules/" in m.name or "/.git/" in "/" + m.name:
                continue
            if _SECRET_NAMES.search(m.name):
                issues.append(f"비밀 파일로 보이는 파일이 포함되어 있습니다: {m.name}")
                continue
            if m.size > MAX_SCAN_FILE or total > MAX_SCAN_TOTAL:
                continue
            total += m.size
            f = tar.extractfile(m)
            data = f.read() if f else b""
            if b"\0" in data[:2048]:
                continue  # 바이너리
            text = data.decode("utf-8", errors="ignore")
            for pat, label in _SECRET_PATTERNS:
                if pat.search(text):
                    issues.append(f"{label} 로 보이는 값이 {m.name} 에 있습니다")
                    break
            if len(issues) >= 10:
                break
    return issues


def decide_publish(kind: str, issues: list) -> tuple:
    """(검수 상태, 메모). 점검에 걸리면 막고(blocked), 정적 앱은 즉시 승인, 서버형 앱은 관리자 승인 대기."""
    if issues:
        return "blocked", "; ".join(issues[:5])
    if kind == "static":
        return "approved", ""
    return "pending", "서버형 앱은 관리자 승인 후 공개됩니다"


def is_admin_email(email: Optional[str]) -> bool:
    return bool(email) and email.lower() in {e.strip().lower() for e in settings.ADMIN_EMAILS.split(",") if e.strip()}


class RateLimiter:
    """키별 슬라이딩 윈도우(초 단위) 요청 수 제한."""

    def __init__(self, limit: int, window: float = 60.0):
        self.limit, self.window = limit, window
        self._hits: dict = defaultdict(deque)

    def allow(self, key) -> bool:
        if self.limit <= 0:
            return True
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        if len(self._hits) > 5000:  # 오래된 키 정리
            for k in [k for k, v in self._hits.items() if not v or now - v[-1] > self.window]:
                del self._hits[k]
        return True
