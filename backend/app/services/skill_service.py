"""GitHub URL 로부터 skill(SKILL.md 포함 디렉터리)을 내려받아 사용자별로 설치한다."""
import asyncio
import io
import os
import re
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Optional
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.skill import Skill
from app.services.sandbox_service import SandboxService, sandbox_manager

MAX_SKILLS_PER_INSTALL = 20
# sandbox 컨테이너 내 skill 저장 위치: /workspace/skills/{name}
SANDBOX_SKILLS_DIR = "/workspace/skills"
_GITHUB_HOSTS = {"github.com", "www.github.com"}
# 다운로드 리다이렉트로 허용되는 호스트 (SSRF 방지)
_ALLOWED_DOWNLOAD_HOSTS = {"api.github.com", "codeload.github.com"}
_NAME_RE = re.compile(r"[^a-z0-9_-]+")


class GithubRef:
    def __init__(self, owner: str, repo: str, ref: Optional[str], subpath: str):
        self.owner, self.repo, self.ref, self.subpath = owner, repo, ref, subpath


def parse_github_url(url: str) -> GithubRef:
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or parsed.hostname not in _GITHUB_HOSTS:
        raise HTTPException(400, "https://github.com/... 형식의 URL만 지원합니다")
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise HTTPException(400, "URL에 owner/repo가 필요합니다")
    owner, repo = parts[0], re.sub(r"\.git$", "", parts[1])
    ref: Optional[str] = None
    subpath = ""
    # /owner/repo/tree/<ref>/<path>  또는  /blob/<ref>/<path>
    # ref에 '/'가 포함된 브랜치명은 지원하지 않는다 (첫 세그먼트를 ref로 취급)
    if len(parts) >= 4 and parts[2] in ("tree", "blob"):
        ref = parts[3]
        subpath = "/".join(parts[4:])
    elif len(parts) > 2:
        raise HTTPException(400, "지원하지 않는 GitHub URL 형식입니다")
    if subpath.endswith("SKILL.md"):
        subpath = str(PurePosixPath(subpath).parent)
        subpath = "" if subpath == "." else subpath
    return GithubRef(owner, repo, ref, subpath)


async def _download_zip(g: GithubRef) -> bytes:
    suffix = f"/{g.ref}" if g.ref else ""
    url = f"https://api.github.com/repos/{g.owner}/{g.repo}/zipball{suffix}"
    limit = settings.SKILL_MAX_DOWNLOAD_MB * 1024 * 1024
    buf = bytearray()
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
            async with client.stream(
                "GET", url, headers={"Accept": "application/vnd.github+json"}
            ) as resp:
                if resp.url.host not in _ALLOWED_DOWNLOAD_HOSTS:
                    raise HTTPException(502, "허용되지 않은 다운로드 호스트입니다")
                if resp.status_code == 404:
                    raise HTTPException(404, "저장소 또는 브랜치를 찾을 수 없습니다 (private 저장소는 지원하지 않습니다)")
                if resp.status_code in (403, 429):
                    raise HTTPException(429, "GitHub API 요청 한도를 초과했습니다. 잠시 후 다시 시도하세요")
                if resp.status_code != 200:
                    raise HTTPException(502, f"GitHub 다운로드 실패 (HTTP {resp.status_code})")
                async for chunk in resp.aiter_bytes():
                    buf.extend(chunk)
                    if len(buf) > limit:
                        raise HTTPException(413, f"저장소가 너무 큽니다 (최대 {settings.SKILL_MAX_DOWNLOAD_MB}MB)")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"GitHub 연결 실패: {e}") from e
    return bytes(buf)


def _parse_frontmatter(text: str) -> dict[str, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*(\n|$)", text, re.DOTALL)
    if not m:
        return {}
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        km = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if km:
            meta[km.group(1)] = km.group(2).strip().strip("\"'")
    return meta


def _safe_name(raw: str) -> str:
    return _NAME_RE.sub("-", raw.strip().lower()).strip("-")[:100]


def _extract_skills(data: bytes, g: GithubRef, dest_root: Path) -> list[dict]:
    """zip 에서 SKILL.md 가 있는 디렉터리를 찾아 dest_root/<name> 에 추출한다."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise HTTPException(502, "잘못된 zip 응답입니다") from e

    infos = [i for i in zf.infolist() if not i.is_dir()]
    # zipball 은 단일 최상위 디렉터리(<owner>-<repo>-<sha>/)로 감싸져 있다
    prefix = infos[0].filename.split("/", 1)[0] + "/" if infos else ""
    base = f"{prefix}{g.subpath.strip('/')}/" if g.subpath else prefix

    skill_dirs = sorted(
        {
            i.filename.rsplit("/", 1)[0] + "/"
            for i in infos
            if i.filename.startswith(base) and PurePosixPath(i.filename).name == "SKILL.md"
        }
    )
    # 루트 SKILL.md 가 있으면 하위 skill 은 무시
    if base in skill_dirs:
        skill_dirs = [base]
    if not skill_dirs:
        raise HTTPException(404, "SKILL.md 를 찾을 수 없습니다")
    if len(skill_dirs) > MAX_SKILLS_PER_INSTALL:
        raise HTTPException(400, f"한 번에 최대 {MAX_SKILLS_PER_INSTALL}개까지 설치할 수 있습니다. 하위 경로 URL을 지정하세요")

    max_extract = settings.SKILL_MAX_EXTRACT_MB * 1024 * 1024
    total = 0
    results: list[dict] = []
    dest_root.mkdir(parents=True, exist_ok=True)

    for sdir in skill_dirs:
        meta = _parse_frontmatter(zf.read(sdir + "SKILL.md").decode("utf-8", errors="replace"))
        fallback = sdir.rstrip("/").rsplit("/", 1)[-1] if sdir != prefix else g.repo
        name = _safe_name(meta.get("name") or fallback)
        if not name:
            raise HTTPException(400, "skill 이름을 결정할 수 없습니다")
        target = (dest_root / name).resolve()
        if dest_root.resolve() not in target.parents:
            raise HTTPException(400, "잘못된 skill 이름입니다")

        tmp = dest_root / f".tmp-{name}"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        for info in infos:
            if not info.filename.startswith(sdir):
                continue
            # 중첩된 다른 skill 디렉터리는 제외하지 않음 (단순화), symlink 는 제외
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                continue
            rel = info.filename[len(sdir):]
            out = (tmp / rel).resolve()
            if tmp.resolve() not in out.parents:  # zip-slip 방지
                continue
            total += info.file_size
            if total > max_extract:
                shutil.rmtree(tmp, ignore_errors=True)
                raise HTTPException(413, f"압축 해제 크기가 너무 큽니다 (최대 {settings.SKILL_MAX_EXTRACT_MB}MB)")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(zf.read(info))

        shutil.rmtree(target, ignore_errors=True)
        tmp.rename(target)
        results.append(
            {"name": name, "description": meta.get("description", ""), "path": str(target)}
        )
    return results


_DIRNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


def _skip_links_filter(member: tarfile.TarInfo, path: str):
    """링크는 건너뛰고(None), 경로 이탈·장치 파일 등은 data 필터가 예외로 거부한다."""
    if member.issym() or member.islnk():
        return None
    return tarfile.data_filter(member, path)


def _import_skill_dir(tar_path: str, dirname: str, dest_root: Path) -> dict:
    """sandbox 에서 내려받은 tar 를 안전하게 풀어 dest_root/<name> 에 설치한다.

    sandbox 안의 파일은 에이전트(LLM)가 만든 신뢰할 수 없는 입력이므로 tarfile 'data' 필터로
    절대경로/상위경로/장치 파일을 거부하고, 심볼릭/하드 링크는 건너뛴다.
    """
    max_extract = settings.SKILL_MAX_EXTRACT_MB * 1024 * 1024
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(tar_path) as tar:
            if sum(m.size for m in tar.getmembers()) > max_extract:
                raise HTTPException(413, f"skill 이 너무 큽니다 (최대 {settings.SKILL_MAX_EXTRACT_MB}MB)")
            tar.extractall(tmp, filter=_skip_links_filter)
        src = Path(tmp) / dirname
        skill_md = src / "SKILL.md"
        if not skill_md.is_file() or skill_md.is_symlink():
            raise HTTPException(404, f"{dirname}/SKILL.md 를 찾을 수 없습니다")
        meta = _parse_frontmatter(skill_md.read_text(encoding="utf-8", errors="replace"))
        name = _safe_name(meta.get("name") or dirname)
        if not name:
            raise HTTPException(400, "skill 이름을 결정할 수 없습니다")

        dest_root.mkdir(parents=True, exist_ok=True)
        target = dest_root / name
        staging = dest_root / f".tmp-{name}"
        shutil.rmtree(staging, ignore_errors=True)
        for f in src.rglob("*"):
            if f.is_symlink() or not f.is_file():
                continue
            out = staging / f.relative_to(src)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, out)
        shutil.rmtree(target, ignore_errors=True)
        staging.rename(target)
    return {"name": name, "description": meta.get("description", ""), "path": str(target), "dirname": dirname}


class SkillService:
    @staticmethod
    async def list_skills(user_id: str, db: AsyncSession) -> list[Skill]:
        r = await db.execute(
            select(Skill).where(Skill.user_id == user_id).order_by(Skill.created_at.desc())
        )
        return list(r.scalars().all())

    @staticmethod
    async def sync_to_sandbox(user_id: str, skills: list[Skill], db: AsyncSession) -> Optional[str]:
        """skill 을 사용자 sandbox 의 /workspace/skills/{name} 으로 복사. 실패 시 오류 메시지 반환."""
        if not skills:
            return None
        try:
            sb = await SandboxService.get_or_create_sandbox(user_id, db)
            for s in skills:
                await sandbox_manager.put_directory(
                    sb.container_id, Path(s.install_path), SANDBOX_SKILLS_DIR, s.name
                )
            return None
        except Exception as e:  # Docker 미실행 등 — 설치 자체는 성공으로 유지
            return f"{type(e).__name__}: {str(e)[:300]}"

    @staticmethod
    async def install(user_id: str, url: str, db: AsyncSession) -> tuple[list[Skill], Optional[str]]:
        g = parse_github_url(url)
        data = await _download_zip(g)
        dest_root = Path(settings.SKILLS_DIR) / user_id
        extracted = await asyncio.to_thread(_extract_skills, data, g, dest_root)

        installed: list[Skill] = []
        for item in extracted:
            r = await db.execute(
                select(Skill).where(Skill.user_id == user_id, Skill.name == item["name"])
            )
            skill = r.scalar_one_or_none()
            if skill:  # 재설치 = 업데이트
                skill.description = item["description"]
                skill.source_url = url
                skill.install_path = item["path"]
            else:
                skill = Skill(
                    user_id=user_id,
                    name=item["name"],
                    description=item["description"],
                    source_url=url,
                    install_path=item["path"],
                )
                db.add(skill)
            installed.append(skill)
        await db.commit()
        for s in installed:
            await db.refresh(s)
        sandbox_error = await SkillService.sync_to_sandbox(user_id, installed, db)
        return installed, sandbox_error

    @staticmethod
    async def import_from_sandbox(
        user_id: str,
        db: AsyncSession,
        names: Optional[list[str]] = None,
        overwrite: bool = False,
    ) -> tuple[list[Skill], list[str]]:
        """sandbox /workspace/skills/<dir> (에이전트가 직접 만든 skill)을 플랫폼에 등록한다.

        names 가 없으면 SKILL.md 가 있는 모든 하위 디렉터리를 대상으로 하며, 이미 등록된
        skill 은 덮어쓰지 않는다 (overwrite=False). 반환: (등록된 skill, 오류 메시지 목록)
        """
        sb = await SandboxService.get_sandbox(user_id, db)
        if not sb or sb.status != "running" or not sb.container_id:
            return [], ["실행 중인 sandbox 가 없습니다"] if names else []
        if not await sandbox_manager.is_running(sb.container_id):
            return [], ["실행 중인 sandbox 가 없습니다"] if names else []

        if names is None:
            _, out, _ = await sandbox_manager.exec_command(
                sb.container_id,
                f'for d in {SANDBOX_SKILLS_DIR}/*/; do [ -f "$d/SKILL.md" ] && basename "$d"; done',
            )
            names = [n.strip() for n in out.splitlines() if n.strip()]

        existing = {s.name: s for s in await SkillService.list_skills(user_id, db)}
        dest_root = Path(settings.SKILLS_DIR) / user_id
        max_bytes = settings.SKILL_MAX_EXTRACT_MB * 1024 * 1024
        imported: list[Skill] = []
        errors: list[str] = []

        for dirname in names:
            if not _DIRNAME_RE.match(dirname):
                errors.append(f"{dirname}: 허용되지 않는 디렉터리 이름")
                continue
            # 이미 등록된 skill 은 자동 가져오기에서 건너뜀 (오래된 사본으로 덮어쓰기 방지)
            if not overwrite and (dirname in existing or _safe_name(dirname) in existing):
                continue
            fd, tmp_tar = tempfile.mkstemp(suffix=".tar")
            os.close(fd)
            try:
                await sandbox_manager.export_path(
                    sb.container_id, f"{SANDBOX_SKILLS_DIR}/{dirname}", tmp_tar, max_bytes
                )
                item = await asyncio.to_thread(_import_skill_dir, tmp_tar, dirname, dest_root)
            except HTTPException as e:
                errors.append(f"{dirname}: {e.detail}")
                continue
            except Exception as e:
                if type(e).__name__ == "NotFound":
                    errors.append(f"{dirname}: sandbox 의 {SANDBOX_SKILLS_DIR}/{dirname} 에 디렉터리가 없습니다")
                else:
                    errors.append(f"{dirname}: {type(e).__name__}: {str(e)[:200]}")
                continue
            finally:
                try:
                    os.unlink(tmp_tar)
                except OSError:
                    pass

            skill = existing.get(item["name"])
            source = f"sandbox:{SANDBOX_SKILLS_DIR}/{dirname}"
            if skill:
                skill.description, skill.source_url, skill.install_path = (
                    item["description"], source, item["path"],
                )
            else:
                skill = Skill(
                    user_id=user_id, name=item["name"], description=item["description"],
                    source_url=source, install_path=item["path"],
                )
                db.add(skill)
            imported.append(skill)
        if imported:
            await db.commit()
            for sk in imported:
                await db.refresh(sk)
        return imported, errors

    @staticmethod
    async def delete(skill_id: str, user_id: str, db: AsyncSession) -> None:
        r = await db.execute(select(Skill).where(Skill.id == skill_id, Skill.user_id == user_id))
        skill = r.scalar_one_or_none()
        if not skill:
            raise HTTPException(404, "Skill not found")
        await asyncio.to_thread(shutil.rmtree, skill.install_path, True)
        sb = await SandboxService.get_sandbox(user_id, db)
        if sb and sb.status == "running":
            try:
                await sandbox_manager.remove_path(sb.container_id, f"{SANDBOX_SKILLS_DIR}/{skill.name}")
            except Exception:
                pass
        await db.delete(skill)
        await db.commit()
