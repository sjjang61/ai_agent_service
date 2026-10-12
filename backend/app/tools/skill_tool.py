from pathlib import Path
from typing import Dict, Optional

from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool

MAX_READ_BYTES = 100 * 1024


class ReadSkillInput(BaseModel):
    name: str = Field(description="Installed skill name (see the 'Installed skills' list)")
    file: str = Field(
        default="SKILL.md",
        description="File inside the skill directory to read (relative path). Defaults to SKILL.md",
    )


class ReadSkillTool(BaseTool):
    name: str = "read_skill"
    description: str = (
        "Read an installed skill's instructions (SKILL.md) or one of its bundled files. "
        "When the user's request matches an installed skill, call this first and follow the instructions. "
        "The result also lists the other files bundled with the skill."
    )
    args_schema: type[BaseModel] = ReadSkillInput
    # {skill_name: install_path} — 해당 사용자의 활성 skill 만 전달된다
    skills: Dict[str, str] = {}

    def _run(self, name: str, file: str = "SKILL.md") -> str:
        install_path = self.skills.get(name)
        if not install_path:
            available = ", ".join(sorted(self.skills)) or "(none)"
            return f"Skill '{name}' not found. Installed skills: {available}"

        root = Path(install_path).resolve()
        target = (root / file).resolve()
        if target != root and root not in target.parents:
            return "Access denied: path is outside the skill directory"
        if not target.is_file():
            return f"File not found in skill '{name}': {file}"

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
        return text

    async def _arun(self, name: str, file: str = "SKILL.md") -> str:
        return self._run(name, file)


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
            return f"Installed skill '{s.name}' (available via read_skill from the next request)."
        return "Failed to install skill: " + ("; ".join(errors) or "not found")


def build_skills_prompt(skills: list) -> str:
    """시스템 프롬프트에 붙일 skill 안내 섹션. skills: Skill 모델 목록."""
    if not skills:
        return (
            "\n\n## Skills\n"
            "새 skill을 만들면 sandbox의 `/workspace/skills/<name>/SKILL.md` (frontmatter에 name, description)에 "
            "작성한 뒤 반드시 `register_skill` 도구로 설치하세요. 파일만 만들어서는 설치되지 않습니다."
        )
    lines = [
        "",
        "## Installed skills",
        "사용자가 설치한 skill 목록입니다. 요청이 어떤 skill의 설명과 맞으면 "
        "`read_skill` 도구로 SKILL.md 를 먼저 읽고 그 지침을 따르세요. "
        "각 skill의 파일(스크립트 포함)은 sandbox의 `/workspace/skills/<name>/` 에도 복사되어 있으므로 "
        "스크립트 실행은 shell_executor/code_executor 로 그 경로에서 하세요. "
        "새 skill을 만들 때는 `/workspace/skills/<name>/SKILL.md` 에 작성한 뒤 반드시 `register_skill` 도구로 "
        "설치하세요 (파일만 만들어서는 설치되지 않으며 read_skill 로 읽을 수 없습니다). "
        "사용 가능한 skill을 묻는 질문에는 이 목록으로 답하세요.",
        "",
    ]
    for s in skills:
        desc = " ".join((s.description or "").split())[:300]
        lines.append(f"- {s.name}: {desc}" if desc else f"- {s.name}")
    return "\n".join(lines)
