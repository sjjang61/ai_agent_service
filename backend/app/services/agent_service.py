"""커스텀 에이전트: 저장·검증·발행·롤백과 실행 설정(AgentRuntime) 해석."""
import copy
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.agent_runtime import AgentRuntime
from app.config import normalize_llm_type
from app.models.agent import Agent, AgentVersion
from app.models.conversation import Conversation
from app.models.scheduled_task import ScheduledTask
from app.schemas.agent import (
    SELECTABLE_TOOLS,
    AgentConfig,
    AgentInput,
    AgentResponse,
    AgentSummary,
    AgentUpdate,
    ValidationIssue,
    VersionResponse,
)
from app.services.schedule_service import aware

MAX_AGENTS_PER_USER = 30
KNOWN_PROVIDERS = {"pet", "openai", "gemini", "anthropic"}
RESERVED_MEMBER_NAMES = {"agentteam", "researchagent", "coderagent", "exploreragent", "mcpagent"}


def _cfg(raw: dict) -> AgentConfig:
    return AgentConfig.model_validate(raw or {})


def _dump(cfg: AgentConfig) -> dict:
    return cfg.model_dump(mode="json")


async def _published(agent: Agent, db: AsyncSession) -> Optional[AgentVersion]:
    if not agent.published_version_id:
        return None
    return await db.get(AgentVersion, agent.published_version_id)


def validate_config(cfg: AgentConfig, user_skills: set, user_mcp: set) -> List[ValidationIssue]:
    """설정을 검사한다. error 가 있으면 발행할 수 없고, warning 은 저장·발행 모두 가능하다."""
    issues: List[ValidationIssue] = []

    def err(path, msg): issues.append(ValidationIssue(level="error", path=path, message=msg))
    def warn(path, msg): issues.append(ValidationIssue(level="warning", path=path, message=msg))

    if not cfg.prompt.instructions.strip():
        warn("prompt.instructions", "지침이 비어 있어 기본 에이전트와 같이 동작합니다.")
    p = cfg.model.llm_provider
    if p and normalize_llm_type(p) not in KNOWN_PROVIDERS:
        err("model.llm_provider", f"지원하지 않는 LLM 종류입니다: {p}")

    allow = set(cfg.tools.allow)
    for n in cfg.tools.allow:
        if n not in SELECTABLE_TOOLS:
            err("tools.allow", f"알 수 없는 도구입니다: {n}")
    if cfg.tools.mode == "selected" and not allow:
        warn("tools.allow", "허용된 도구가 없어 대화만 할 수 있습니다.")

    if cfg.skills.mode == "selected":
        for n in cfg.skills.names:
            if n not in user_skills:
                warn("skills.names", f"설치되어 있지 않은 스킬입니다: {n}")
    if cfg.mcp.mode == "selected":
        for s in cfg.mcp.servers:
            if s.name not in user_mcp:
                warn("mcp.servers", f"등록되어 있지 않은 MCP 서버입니다: {s.name}")

    team = cfg.team
    if team.mode == "none" and team.members:
        warn("team.members", "팀 구성이 '서브에이전트 없음'이라 정의한 서브에이전트는 사용되지 않습니다.")
    if team.mode == "custom":
        if not team.members:
            warn("team.members", "서브에이전트가 없어 리더 단독으로 실행됩니다.")
        seen = set()
        for i, m in enumerate(team.members):
            key = m.name.lower()
            if key in seen:
                err(f"team.members[{i}].name", f"서브에이전트 이름이 중복됩니다: {m.name}")
            if key in RESERVED_MEMBER_NAMES:
                err(f"team.members[{i}].name", f"예약된 이름입니다: {m.name}")
            seen.add(key)
            for n in m.tools:
                if n not in SELECTABLE_TOOLS:
                    err(f"team.members[{i}].tools", f"알 수 없는 도구입니다: {n}")
                elif cfg.tools.mode == "selected" and n not in allow:
                    err(f"team.members[{i}].tools", f"에이전트의 허용 도구에 없는 도구입니다: {n}")
            if not m.role.strip():
                err(f"team.members[{i}].role", "서브에이전트의 역할 설명이 필요합니다.")
    return issues


class AgentService:
    @staticmethod
    async def _user_resources(user_id: str, db: AsyncSession) -> tuple:
        from app.services.mcp_service import MCPService
        from app.services.skill_service import SkillService

        skills = {s.name for s in await SkillService.list_skills(user_id, db)}
        mcp = {c.name for c in await MCPService.get_user_configs(user_id, db)}
        return skills, mcp

    @staticmethod
    async def validate(user_id: str, cfg: AgentConfig, db: AsyncSession) -> List[ValidationIssue]:
        skills, mcp = await AgentService._user_resources(user_id, db)
        return validate_config(cfg, skills, mcp)

    # ---- 조회
    @staticmethod
    async def list_agents(user_id: str, db: AsyncSession) -> List[Agent]:
        r = await db.execute(select(Agent).where(Agent.user_id == user_id).order_by(Agent.updated_at.desc()))
        return list(r.scalars().all())

    @staticmethod
    async def get(user_id: str, agent_id: str, db: AsyncSession) -> Agent:
        r = await db.execute(select(Agent).where(Agent.id == agent_id, Agent.user_id == user_id))
        agent = r.scalar_one_or_none()
        if not agent:
            raise HTTPException(404, "에이전트를 찾을 수 없습니다")
        return agent

    # ---- 응답 변환
    @staticmethod
    async def to_response(agent: Agent, db: AsyncSession) -> AgentResponse:
        ver = await _published(agent, db)
        draft = _cfg(agent.draft_config)
        return AgentResponse(
            id=agent.id, name=agent.name, description=agent.description, icon=agent.icon, config=draft,
            published_version=ver.version if ver else None, published_at=aware(ver.created_at) if ver else None,
            has_unpublished_changes=bool(ver is None or _dump(_cfg(ver.config)) != _dump(draft)),
            created_at=aware(agent.created_at), updated_at=aware(agent.updated_at),
        )

    @staticmethod
    async def to_summary(agent: Agent, db: AsyncSession) -> AgentSummary:
        ver = await _published(agent, db)
        draft = _cfg(agent.draft_config)
        shown = _cfg(ver.config) if ver else draft  # 선택 목록에는 발행된 설정의 추천 질문을 보여 준다
        return AgentSummary(
            id=agent.id, name=agent.name, description=agent.description, icon=agent.icon,
            published_version=ver.version if ver else None,
            has_unpublished_changes=bool(ver is None or _dump(_cfg(ver.config)) != _dump(draft)),
            starters=shown.prompt.starters, updated_at=aware(agent.updated_at),
        )

    # ---- 생성·수정·삭제
    @staticmethod
    async def create(user_id: str, data: AgentInput, db: AsyncSession) -> Agent:
        n = (await db.execute(select(func.count()).select_from(Agent).where(Agent.user_id == user_id))).scalar() or 0
        if n >= MAX_AGENTS_PER_USER:
            raise HTTPException(400, f"에이전트는 최대 {MAX_AGENTS_PER_USER}개까지 만들 수 있습니다")
        agent = Agent(
            user_id=user_id, name=data.name.strip(), description=data.description.strip(), icon=data.icon or "🤖",
            draft_config=_dump(data.config),
        )
        db.add(agent)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(409, f"같은 이름의 에이전트가 이미 있습니다: {data.name}")
        await db.refresh(agent)
        return agent

    @staticmethod
    async def update(user_id: str, agent_id: str, data: AgentUpdate, db: AsyncSession) -> Agent:
        agent = await AgentService.get(user_id, agent_id, db)
        if data.name is not None:
            agent.name = data.name.strip()
        if data.description is not None:
            agent.description = data.description.strip()
        if data.icon is not None:
            agent.icon = data.icon or "🤖"
        if data.config is not None:
            agent.draft_config = _dump(data.config)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(409, f"같은 이름의 에이전트가 이미 있습니다: {data.name}")
        await db.refresh(agent)
        return agent

    @staticmethod
    async def duplicate(user_id: str, agent_id: str, db: AsyncSession) -> Agent:
        src = await AgentService.get(user_id, agent_id, db)
        names = {a.name for a in await AgentService.list_agents(user_id, db)}
        base, i = f"{src.name} 복사본"[:90], 1
        name = base
        while name in names:
            i += 1
            name = f"{base} {i}"
        return await AgentService.create(
            user_id, AgentInput(name=name, description=src.description, icon=src.icon, config=_cfg(src.draft_config)), db
        )

    @staticmethod
    async def delete(user_id: str, agent_id: str, db: AsyncSession) -> None:
        agent = await AgentService.get(user_id, agent_id, db)
        used = (await db.execute(
            select(func.count()).select_from(ScheduledTask).where(ScheduledTask.agent_id == agent_id)
        )).scalar() or 0
        if used:
            raise HTTPException(409, f"이 에이전트를 사용하는 예약 작업이 {used}개 있습니다. 예약을 먼저 삭제하거나 다른 에이전트로 바꾸세요")
        # 기존 대화는 유지하되 에이전트 연결만 끊는다 (이후 기본 에이전트로 동작)
        await db.execute(update(Conversation).where(Conversation.agent_id == agent_id).values(agent_id=None, agent_version_id=None))
        await db.execute(delete(AgentVersion).where(AgentVersion.agent_id == agent_id))
        await db.delete(agent)
        await db.commit()

    # ---- 발행·버전
    @staticmethod
    async def publish(user_id: str, agent_id: str, note: str, db: AsyncSession) -> tuple:
        agent = await AgentService.get(user_id, agent_id, db)
        cfg = _cfg(agent.draft_config)
        issues = await AgentService.validate(user_id, cfg, db)
        errors = [i for i in issues if i.level == "error"]
        if errors:
            raise HTTPException(422, "발행할 수 없습니다: " + "; ".join(f"{e.path}: {e.message}" for e in errors[:5]))
        last = (await db.execute(select(func.max(AgentVersion.version)).where(AgentVersion.agent_id == agent_id))).scalar() or 0
        ver = AgentVersion(agent_id=agent_id, version=last + 1, config=copy.deepcopy(_dump(cfg)), note=note.strip())
        db.add(ver)
        await db.flush()
        agent.published_version_id = ver.id
        await db.commit()
        await db.refresh(ver)
        return ver, issues

    @staticmethod
    async def versions(user_id: str, agent_id: str, db: AsyncSession) -> List[VersionResponse]:
        agent = await AgentService.get(user_id, agent_id, db)
        rows = (await db.execute(
            select(AgentVersion).where(AgentVersion.agent_id == agent_id).order_by(AgentVersion.version.desc())
        )).scalars().all()
        return [
            VersionResponse(id=v.id, version=v.version, note=v.note, config=_cfg(v.config),
                            created_at=aware(v.created_at), is_current=(v.id == agent.published_version_id))
            for v in rows
        ]

    @staticmethod
    async def restore_version_to_draft(user_id: str, agent_id: str, version: int, db: AsyncSession) -> Agent:
        """이전 버전의 설정을 초안으로 되돌린다 (발행은 따로 한다)."""
        agent = await AgentService.get(user_id, agent_id, db)
        ver = (await db.execute(
            select(AgentVersion).where(AgentVersion.agent_id == agent_id, AgentVersion.version == version)
        )).scalar_one_or_none()
        if not ver:
            raise HTTPException(404, "해당 버전이 없습니다")
        agent.draft_config = copy.deepcopy(ver.config)
        await db.commit()
        await db.refresh(agent)
        return agent

    @staticmethod
    async def set_current_version(user_id: str, agent_id: str, version: int, db: AsyncSession) -> Agent:
        """롤백: 지정한 이전 버전을 현재 발행 버전으로 되돌린다 (새 대화·예약이 이 버전을 쓴다)."""
        agent = await AgentService.get(user_id, agent_id, db)
        ver = (await db.execute(
            select(AgentVersion).where(AgentVersion.agent_id == agent_id, AgentVersion.version == version)
        )).scalar_one_or_none()
        if not ver:
            raise HTTPException(404, "해당 버전이 없습니다")
        agent.published_version_id = ver.id
        await db.commit()
        await db.refresh(agent)
        return agent

    # ---- 실행 설정 해석
    @staticmethod
    async def require_published(user_id: str, agent_id: str, db: AsyncSession) -> tuple:
        agent = await AgentService.get(user_id, agent_id, db)
        ver = await _published(agent, db)
        if ver is None:
            raise HTTPException(400, f"발행되지 않은 에이전트입니다: {agent.name}. 먼저 발행하세요")
        return agent, ver

    @staticmethod
    async def runtime_for_conversation(
        conv: Conversation, db: AsyncSession, draft_override: Optional[AgentConfig] = None
    ) -> Optional[AgentRuntime]:
        """대화에 연결된 에이전트의 실행 설정. 연결이 없거나 에이전트가 사라졌으면 None(기본 에이전트)."""
        if not conv.agent_id:
            return None
        agent = await db.get(Agent, conv.agent_id)
        if agent is None or agent.user_id != conv.user_id:
            return None
        if conv.is_test:  # 빌더 미리보기: 저장 전 편집 내용(override) 또는 초안으로 실행
            return AgentRuntime(config=draft_override or _cfg(agent.draft_config), agent_id=agent.id, agent_name=agent.name, version=None)
        ver = await db.get(AgentVersion, conv.agent_version_id) if conv.agent_version_id else None
        ver = ver or await _published(agent, db)
        if ver is None:
            return None
        return AgentRuntime(config=_cfg(ver.config), agent_id=agent.id, agent_name=agent.name, version=ver.version)

    @staticmethod
    async def runtime_for_task(task: ScheduledTask, db: AsyncSession) -> Optional[AgentRuntime]:
        """예약 작업은 실행 시점의 최신 발행 버전을 쓴다. 에이전트가 없거나 발행되지 않았으면 예외."""
        if not task.agent_id:
            return None
        agent = await db.get(Agent, task.agent_id)
        if agent is None or agent.user_id != task.user_id:
            raise RuntimeError("예약에 지정된 에이전트가 삭제되었습니다")
        ver = await _published(agent, db)
        if ver is None:
            raise RuntimeError(f"예약에 지정된 에이전트 '{agent.name}'가 발행되지 않았습니다")
        return AgentRuntime(config=_cfg(ver.config), agent_id=agent.id, agent_name=agent.name, version=ver.version)
