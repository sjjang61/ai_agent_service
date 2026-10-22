from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import Literal

LLMType = Literal["pet", "openai", "gemini", "anthropic"]

# 별칭 → 정식 LLM_TYPE (오타 'antropic' 및 기존 provider 이름 호환)
_LLM_TYPE_ALIASES = {
    "antropic": "anthropic",
    "petagent": "pet",
    "google": "gemini",
}


def normalize_llm_type(value: str) -> str:
    v = (value or "").strip().lower()
    return _LLM_TYPE_ALIASES.get(v, v)

# config.py 위치: backend/app/config.py → 루트 .env: ../../.env
_ENV_FILE = Path(__file__).parent.parent.parent / ".env"


class Settings(BaseSettings):
    # App
    APP_ENV: Literal["development", "production"] = "development"
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database (개별 설정)
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "password"
    DB_NAME: str = "super_agent"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_USER: str = ""
    REDIS_PASSWORD: str = ""

    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_USER and self.REDIS_PASSWORD:
            return f"redis://{self.REDIS_USER}:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}"
        elif self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}"

    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # LLM Providers
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    # 사용할 LLM 종류: pet | openai | gemini | anthropic
    LLM_TYPE: LLMType = "pet"
    # LLM_TYPE 별 모델 (pet 은 PET_MODEL_ID 사용)
    OPENAI_MODEL: str = "gpt-4o"
    GEMINI_MODEL: str = "gemini-2.5-flash"
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5"

    @field_validator("LLM_TYPE", mode="before")
    @classmethod
    def _normalize_llm_type(cls, v):
        return normalize_llm_type(v) if isinstance(v, str) else v

    def default_model_for(self, llm_type: str) -> str:
        return {
            "pet": self.PET_MODEL_ID,
            "openai": self.OPENAI_MODEL,
            "gemini": self.GEMINI_MODEL,
            "anthropic": self.ANTHROPIC_MODEL,
        }.get(llm_type, "")

    # Agent
    AGENT_MAX_ITERATIONS: int = 25
    AGENT_TIMEOUT_SECONDS: int = 300
    AGENT_MEMORY_WINDOW: int = 20
    # 에이전트 실행 엔진: agno (멀티에이전트 Team) | langgraph (단일 ReAct 에이전트)
    AGENT_ENGINE: Literal["agno", "langgraph"] = "agno"

    # PetAgent (사내 LLM — OpenAI-compatible)
    PET_AGENT_URL: str = ""
    PET_MODEL_ID: str = ""
    PET_API_KEY: str = "NONE"
    PET_TIMEOUT: float = 60.0
    PET_MCP_SERVER_URL: str = ""
    PET_STREAMING: bool = False  # PetAgent 서버가 SSE 스트리밍을 지원하면 true
    # reasoning 모델(gpt-5 계열 등)은 tool 사용 시 chat/completions 에서 "none" 이어야 한다. 빈 값이면 미전송
    PET_REASONING_EFFORT: str = "none"
    OPENAI_REASONING_EFFORT: str = ""

    # Tools
    TAVILY_API_KEY: str = ""
    SERPAPI_KEY: str = ""
    CRAWLER_HEADLESS: bool = True
    CRAWLER_TIMEOUT_MS: int = 30000

    # Sandbox
    SANDBOX_IMAGE: str = "ai-agent-sandbox:latest"
    SANDBOX_CPU_LIMIT: str = "1.0"
    SANDBOX_MEMORY_LIMIT: str = "512m"
    SANDBOX_NETWORK: str = "sandbox-network"
    SANDBOX_TTL_HOURS: int = 24
    SANDBOX_POOL_MIN: int = 3
    SANDBOX_POOL_MAX: int = 50

    # MCP 도구 노출 방식: lazy = 목록만 프롬프트에 두고 load_mcp_tool/call_mcp_tool/run_mcp_code 로 사용,
    #                    direct = 모든 MCP 도구를 개별 도구로 직접 등록 (스키마가 매번 LLM 컨텍스트에 포함됨)
    MCP_TOOL_MODE: Literal["lazy", "direct"] = "lazy"

    # Sandbox 백업/복구 (MinIO). MINIO_ENDPOINT 가 비어 있으면 백업 기능 비활성화
    MINIO_ENDPOINT: str = ""  # host:port
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_SECURE: bool = False
    MINIO_BUCKET: str = "sandbox-sessions"
    SANDBOX_MAX_RUNNING_PER_USER: int = 5  # 한 사용자가 동시에 실행할 수 있는 sandbox 수 (넘으면 가장 오래 쓰지 않은 것을 백업 후 종료)
    SANDBOX_IDLE_MINUTES: int = 5  # last_used_at 기준 미사용 시간이 지나면 백업 후 종료
    SANDBOX_REAPER_INTERVAL_SECONDS: int = 60
    SANDBOX_BACKUP_MAX_MB: int = 500  # 초과하면 백업 실패 처리 (sandbox 는 종료하지 않음)

    # 파일 도구: 공개 다운로드 링크(publish_file/write_file) · URL 다운로드(download_file)
    PUBLIC_BASE_URL: str = "http://localhost:8500"  # 공개 링크에 붙는 백엔드 외부 접근 주소
    PUBLISH_DIR: str = str(Path(__file__).parent.parent.parent / "data" / "published")
    PUBLISH_EXPIRE_HOURS: int = 24
    PUBLISH_MAX_MB: int = 100
    DOWNLOAD_MAX_MB: int = 50

    # 브라우저 에이전트 (cli_browser_agent)
    BROWSER_MAX_STEPS: int = 30
    BROWSER_TIMEOUT_SECONDS: int = 300

    # 채팅 첨부 파일 업로드 (sandbox /workspace/uploads/)
    UPLOAD_MAX_MB: int = 50
    UPLOAD_FOLDER_MAX_FILES: int = 300  # 폴더 업로드: 최대 파일 수
    UPLOAD_FOLDER_MAX_MB: int = 100  # 폴더 업로드: 전체 크기
    REFERENCE_MAX_CHARS: int = 12000  # 참조(페이지·이전 대화) 하나당 에이전트에게 전달하는 최대 글자 수

    # 산출물(artifacts) 보기
    ARTIFACT_PREVIEW_MAX_KB: int = 200
    ARTIFACT_MAX_DOWNLOAD_MB: int = 100
    ARTIFACT_LIST_LIMIT: int = 2000

    # Skills (사용자별 설치 경로: SKILLS_DIR/{user_id}/{skill_name})
    SKILLS_DIR: str = str(Path(__file__).parent.parent.parent / "data" / "skills")
    SKILL_MAX_DOWNLOAD_MB: int = 50
    SKILL_MAX_EXTRACT_MB: int = 20

    # Memory (장기/단기 메모리)
    ENABLE_MEMORY_EXTRACTION: bool = True  # 대화에서 자동 메모리 추출
    ENABLE_CONVERSATION_SUMMARY: bool = True  # 컨텍스트 창에서 밀려난 오래된 메시지의 롤링 요약
    MEMORY_CONTEXT_LIMIT: int = 15  # Agent 프롬프트에 주입할 최대 메모리 개수
    SHORT_TERM_MEMORY_TTL: int = 86400  # 단기 메모리 TTL (초, 기본 24시간)

    # RAG (Retrieval-Augmented Generation)
    CHROMA_PERSIST_DIR: str = str(Path(__file__).parent.parent.parent / "data" / "chroma")
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    RAG_TOP_K: int = 5  # 검색 시 상위 K개 청크
    RAG_MAX_FILE_SIZE_MB: int = 50  # 문서 최대 크기

    # 예약 작업 (스케줄러)
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_POLL_SECONDS: int = 30  # 실행 시각이 된 작업을 찾는 주기
    SCHEDULER_MAX_CONCURRENT: int = 3  # 동시에 실행할 예약 작업 수
    SCHEDULER_MISFIRE_GRACE_SECONDS: int = 3600  # 서버 중단 등으로 이 시간 넘게 늦으면 실행하지 않고 건너뜀
    SCHEDULER_RUN_TIMEOUT_SECONDS: int = 600  # 회차당 최대 실행 시간
    SCHEDULER_MAX_TASKS_PER_USER: int = 10
    SCHEDULER_MAX_CONSECUTIVE_FAILURES: int = 3  # 연속 실패 시 자동 일시중지
    SCHEDULER_MIN_INTERVAL_HOURS: int = 1  # '매 N시간' 반복의 최소 간격
    SCHEDULER_DEFAULT_TIMEZONE: str = "Asia/Seoul"

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:80",
    ]

    class Config:
        env_file = str(_ENV_FILE)
        env_file_encoding = "utf-8"


settings = Settings()
