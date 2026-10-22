from pathlib import Path
from typing import Dict, Optional

from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool

from app.agent.prompts import load, render

MAX_READ_BYTES = 100 * 1024


class LoadSkillInput(BaseModel):
    name: str = Field(description="Installed skill name (see the 'Installed skills' list)")
    file: str = Field(
        default="SKILL.md",
        description="File inside the skill directory to read (relative path). Defaults to SKILL.md",
    )


class LoadSkillTool(BaseTool):
    name: str = "load_skill"
    description: str = (
        "Load the instructions (SKILL.md) of an installed skill that matches the type of task, or one of its bundled files. "
        "When the user's request matches an installed skill, call this first and follow the instructions. "
        "The result also lists the other files bundled with the skill."
    )
    args_schema: type[BaseModel] = LoadSkillInput
    # {skill_name: install_path} — 해당 사용자의 활성 skill 만 전달된다
    skills: Dict[str, str] = {}

    user_id: str = ""  # sandbox 에 skill 파일이 있는지 확인·복사하는 데 쓴다

    def _load(self, name: str, file: str = "SKILL.md") -> tuple[str, bool]:
        """호스트에 설치된 skill 파일을 읽는다. 반환: (텍스트, 성공 여부)."""
        install_path = self.skills.get(name)
        if not install_path:
            available = ", ".join(sorted(self.skills)) or "(none)"
            return f"Skill '{name}' not found. Installed skills: {available}", False

        root = Path(install_path).resolve()
        target = (root / file).resolve()
        if target != root and root not in target.parents:
            return "Access denied: path is outside the skill directory", False
        if not target.is_file():
            return f"File not found in skill '{name}': {file}", False

        data = target.read_bytes()[: MAX_READ_BYTES + 1]
        truncated = len(data) > MAX_READ_BYTES
        text = data[:MAX_READ_BYTES].decode("utf-8", errors="replace")
        if truncated:
            text += "\n\n[truncated]"

        if file == "SKILL.md":
            others = sorted(
                str(p.relative_to(root))
                for p in root.rglob("*")
                if p.is_file() and p.name != "SKILL.md"
            )[:50]
            if others:
                text += "\n\n---\nOther files in this skill (read with the `file` argument):\n" + "\n".join(
                    f"- {o}" for o in others
                )
        return text, True

    def _run(self, name: str, file: str = "SKILL.md") -> str:
        return self._load(name, file)[0]

    async def _sandbox_note(self, name: str) -> str:
        """SKILL.md 를 읽은 뒤 붙이는 sandbox 상태 안내. 실행 중인 sandbox 에 skill 이 없으면 그 자리에서 복사한다.
        (load_skill 은 호스트 사본을 읽으므로, 이 확인이 없으면 sandbox 에 파일이 없어도 '성공'으로 보인다.)"""
        from app.services.skill_service import SANDBOX_SKILLS_DIR

        path = f"{SANDBOX_SKILLS_DIR}/{name}/"
        if not self.user_id:
            return ""
        try:
            from app.db.session import AsyncSessionLocal
            from app.services.sandbox_service import SandboxService, sandbox_manager
            from app.services.skill_service import SkillService

            async with AsyncSessionLocal() as db:
                sb = await SandboxService.get_sandbox(self.user_id, db)
                if not sb or sb.status != "running" or not sb.container_id or not await sandbox_manager.is_running(sb.container_id):
                    return "\n\n" + render("tool_result_skill_no_sandbox", path=path)
                mine = [s for s in await SkillService.list_skills(self.user_id, db) if s.name == name]
                copied = await SkillService.ensure_in_sandbox(sb.container_id, mine)
            if copied:
                return "\n\n" + render("tool_result_skill_copied_to_sandbox", path=path)
            return "\n\n" + render("tool_result_skill_in_sandbox", path=path)
        except Exception as e:  # noqa: BLE001 — 확인 실패가 skill 읽기 자체를 막지 않게 한다
            return "\n\n" + render("tool_result_skill_sandbox_error", error=f"{type(e).__name__}: {str(e)[:120]}", path=path)

    async def _arun(self, name: str, file: str = "SKILL.md") -> str:
        text, ok = self._load(name, file)
        if ok and file == "SKILL.md":
            text += await self._sandbox_note(name)
        return text


class RegisterSkillInput(BaseModel):
    name: str = Field(
        description="Directory name of the skill you created under /workspace/skills/ in the sandbox"
    )


class RegisterSkillTool(BaseTool):
    name: str = "register_skill"
    description: str = (
        "Install (register) a skill you created in the sandbox at /workspace/skills/<name>/ "
        "so it becomes an installed skill. The directory must contain SKILL.md with YAML "
        "frontmatter (name, description). Call this after creating or editing a skill; "
        "a skill that is only written to the sandbox is NOT installed."
    )
    args_schema: type[BaseModel] = RegisterSkillInput
    user_id: str = ""

    def _run(self, name: str) -> str:
        return "register_skill supports async execution only"

    async def _arun(self, name: str) -> str:
        from app.db.session import AsyncSessionLocal
        from app.services.skill_service import SkillService

        async with AsyncSessionLocal() as db:
            imported, errors = await SkillService.import_from_sandbox(
                self.user_id, db, names=[name.strip().strip("/")], overwrite=True
            )
        if imported:
            s = imported[0]
            return f"Installed skill '{s.name}' (available via load_skill from the next request)."
        return "Failed to install skill: " + ("; ".join(errors) or "not found")


def build_skills_prompt(skills: list) -> str:
    """시스템 프롬프트에 붙일 skill 안내 섹션 (문구는 prompts/skills_*.md). skills: Skill 모델 목록."""
    if not skills:
        return "\n\n" + load("skills_none")
    lines = []
    for s in skills:
        desc = " ".join((s.description or "").split())[:300]
        lines.append(f"- {s.name}: {desc}" if desc else f"- {s.name}")
    return "\n" + render("skills_installed", skills="\n".join(lines))
