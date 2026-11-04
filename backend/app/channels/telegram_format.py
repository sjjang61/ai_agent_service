"""마크다운 답변을 Telegram 메시지로 바꾼다 (HTML 부분집합 + 4096자 분할)."""
import html
import re

LIMIT = 4096
CHUNK = 3500  # HTML 태그가 붙으면 늘어나므로 여유를 둔다

_FENCE = re.compile(r"^```")


def split_markdown(text: str, size: int = CHUNK) -> list[str]:
    """줄 단위로 나누되 코드 블록이 쪼개지면 각 조각에서 닫고 다시 연다. 한 줄이 size 보다 길면 강제로 자른다."""
    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0
    fence = ""  # 열려 있는 코드 블록의 여는 줄 (예: "```python")

    def flush():
        nonlocal cur, cur_len
        if not cur:
            return
        body = "\n".join(cur)
        if fence:
            body += "\n```"
        chunks.append(body)
        cur = [fence] if fence else []
        cur_len = len(fence) + 1 if fence else 0

    for line in (text or "").split("\n"):
        pieces = [line[i:i + size] for i in range(0, len(line), size)] or [""]
        for piece in pieces:
            if cur_len + len(piece) + 1 > size:
                flush()
            cur.append(piece)
            cur_len += len(piece) + 1
        if _FENCE.match(line.strip()):
            fence = "" if fence else line.strip()
    if cur and any(c.strip() for c in cur):
        chunks.append("\n".join(cur))
    return [c for c in chunks if c.strip()]


def _inline(text: str) -> str:
    """코드 블록이 아닌 줄의 인라인 서식. 먼저 이스케이프한 뒤 허용 태그만 만든다."""
    spans: list[str] = []

    def stash(m):
        spans.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(spans) - 1}\x00"

    text = re.sub(r"`([^`\n]+)`", stash, text)
    text = html.escape(text, quote=False)
    text = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", text, flags=re.M)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(
        r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)",
        lambda m: f'<a href="{html.escape(html.unescape(m.group(2)), quote=True)}">{m.group(1)}</a>',
        text,
    )
    return re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], text)


def to_telegram_html(markdown: str) -> str:
    out: list[str] = []
    lines = (markdown or "").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if _FENCE.match(line.strip()):  # 코드 블록
            body = []
            i += 1
            while i < len(lines) and not _FENCE.match(lines[i].strip()):
                body.append(lines[i])
                i += 1
            i += 1
            out.append(f"<pre>{html.escape(chr(10).join(body))}</pre>")
        elif line.lstrip().startswith("|"):  # 표 → 고정폭 (구분선 줄은 버린다)
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                if not re.fullmatch(r"[\s|:\-]+", lines[i]):
                    rows.append(lines[i].strip())
                i += 1
            out.append(f"<pre>{html.escape(chr(10).join(rows))}</pre>")
        else:
            out.append(_inline(line))
            i += 1
    return "\n".join(out)


def render_messages(markdown: str) -> list[tuple[str, str]]:
    """[(html, plain)] — HTML 파싱이 거부되면 plain 으로 다시 보낸다."""
    return [(to_telegram_html(c)[:LIMIT], c[:LIMIT]) for c in split_markdown(markdown)]


def table_widget_text(spec: dict) -> str:
    """표 위젯을 마크다운 표로 (Telegram 에서는 고정폭으로 보인다)."""
    cols = [str(c) for c in spec.get("columns", [])]
    if not cols:
        return ""
    lines = ["| " + " | ".join(cols) + " |"]
    for row in spec.get("rows", [])[:50]:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)
