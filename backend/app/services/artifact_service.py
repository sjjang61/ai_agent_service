"""sandbox /workspace 의 산출물(artifacts) 목록·미리보기·다운로드 로직."""
import posixpath
from datetime import datetime, timezone
from typing import Optional

from app.config import settings

IMAGE_EXT = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif",
             "webp": "image/webp", "svg": "image/svg+xml", "bmp": "image/bmp"}
TEXT_EXT = {"txt", "md", "markdown", "json", "jsonl", "csv", "tsv", "py", "js", "jsx", "ts", "tsx", "html", "htm",
            "css", "scss", "yml", "yaml", "xml", "log", "sh", "bash", "sql", "ini", "toml", "cfg", "conf", "env",
            "java", "c", "h", "cpp", "go", "rs", "rb", "php", "r", "ipynb", "tex", "rst"}
DOC_EXT = {"pdf": "pdf", "pptx": "office", "ppt": "office", "docx": "office", "doc": "office",
           "xlsx": "office", "xls": "office", "hwp": "office", "hwpx": "office"}
ARCHIVE_EXT = {"zip", "tar", "gz", "tgz", "bz2", "xz", "7z", "rar"}

# 숨김(dot) 항목은 기본적으로 제외하고, 어떤 경우에도 아래 디렉터리는 제외한다
_ALWAYS_PRUNE = ("node_modules", "__pycache__", ".git", ".cache", ".local", ".npm", ".ipython", ".config")


def classify(name: str) -> tuple[str, Optional[str]]:
    """(kind, mime) — kind: image | text | pdf | office | archive | other"""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext in IMAGE_EXT:
        return "image", IMAGE_EXT[ext]
    if ext in TEXT_EXT:
        return "text", "text/plain"
    if ext in DOC_EXT:
        return DOC_EXT[ext], None
    if ext in ARCHIVE_EXT:
        return "archive", None
    return "other", None


def list_command(include_hidden: bool) -> str:
    prune = " -o ".join(f"-name {n}" for n in _ALWAYS_PRUNE)
    if not include_hidden:
        prune = "-name '.*' -o " + prune
    limit = settings.ARTIFACT_LIST_LIMIT + 1
    return (
        f"find /workspace -mindepth 1 \\( {prune} \\) -prune -o -type f "
        f"-printf '%s\\t%T@\\t%P\\n' 2>/dev/null | head -n {limit}"
    )


def parse_listing(stdout: str) -> tuple[list[dict], bool]:
    files: list[dict] = []
    for line in stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        size, mtime, path = parts
        try:
            modified = datetime.fromtimestamp(float(mtime), tz=timezone.utc).isoformat()
            size_i = int(size)
        except ValueError:
            continue
        name = posixpath.basename(path)
        kind, mime = classify(name)
        files.append({"path": path, "name": name, "size": size_i, "modified": modified, "kind": kind, "mime": mime})
    truncated = len(files) > settings.ARTIFACT_LIST_LIMIT
    files = files[: settings.ARTIFACT_LIST_LIMIT]
    files.sort(key=lambda f: f["modified"], reverse=True)
    return files, truncated
