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


# 에이전트 응답 모니터링 도구 (AGENT_MONITORING_TYPE). 'opic' 같은 오타·별칭도 받는다
MonitoringType = Literal["none", "opik", "langfuse"]
_MONITORING_ALIASES = {"": "none", "off": "none", "false": "none", "0": "none", "disabled": "none", "opic": "opik", "comet": "opik"}


def normalize_monitoring_type(value: str) -> str:
    v = (value or "").strip().lower()
    return _MONITORING_ALIASES.get(v, v)


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

    # 에이전트 응답 모니터링 (트레이스·지연·토큰·오류·평가). none | opik | langfuse — OpenTelemetry(OTLP)로 내보내므로 값만 바꾸면 도구를 바꿀 수 있다.
    # 프롬프트·도구 결과 전문을 그대로 저장한다 → 반드시 자체 호스팅 서버를 쓴다 (infra/monitoring/opik).
    AGENT_MONITORING_TYPE: MonitoringType = "none"
    MONITORING_SERVICE_NAME: str = "ai-agent-backend"
    MONITORING_SAMPLE_RATE: float = 1.0  # 0~1: 트레이스 표본 비율
    MONITORING_MAX_SPAN_ATTRIBUTES: int = 2000  # 스팬 하나에 붙일 수 있는 속성 수 (OTel 기본 128 은 긴 대화에서 모자란다)
    # LangChain 전체 계측: 직접 호출(라우터·메모리 추출·위키 등)과 LangGraph 엔진이 기록되지만, Agno 가 LangChain 도구를 부르는 경로에서는
    # 같은 도구 호출 스팬이 두 번 생긴다(P0 확인). 기본은 끄고, 직접 호출 지점은 콜백으로 따로 계측한다(P1).
    MONITORING_LANGCHAIN: bool = False
    OPIK_URL: str = "http://localhost:15174"  # infra/monitoring/opik 의 NGINX_PORT. Opik Cloud 는 https://www.comet.com/opik
    OPIK_PROJECT_NAME: str = "ai-agent-platform"
    OPIK_WORKSPACE: str = "default"
    OPIK_API_KEY: str = ""  # 자체 호스팅은 비워 둔다 (Opik Cloud 전용)
    LANGFUSE_HOST: str = "http://localhost:3000"
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    # LLM_TYPE 별 모델 (pet 은 PET_MODEL_ID 사용)
    OPENAI_MODEL: str = "gpt-4o"
    GEMINI_MODEL: str = "gemini-2.5-flash"
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5"

    @field_validator("AGENT_MONITORING_TYPE", mode="before")
    @classmethod
    def _normalize_monitoring_type(cls, v):
        return normalize_monitoring_type(v) if isinstance(v, str) else v

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
    # 이미지 생성(generate_image)과 공개 업로드(upload_to_minio): 결과를 공개 읽기 버킷에 올리고 공개 URL 로 접근한다
    IMAGE_GENERATION_ENABLED: bool = True
    OPENAI_IMAGE_MODEL: str = "gpt-image-2"  # OpenAI 가 이미지 모델을 바꾸므로 코드에 박지 않고 설정으로 고른다
    IMAGE_DEFAULT_SIZE: str = "1024x1024"
    IMAGE_DAILY_LIMIT: int = 30  # 사용자당 하루 생성 한도 (0 이면 제한 없음, 서버 재시작 시 초기화)
    IMAGE_TIMEOUT_SECONDS: int = 180
    MINIO_PUBLIC_BUCKET: str = "agent-public"  # 익명 읽기(GetObject)가 열리는 버킷. 비밀 파일을 올리지 말 것
    MINIO_PUBLIC_URL: str = ""  # 브라우저가 접근하는 MinIO 주소. 비워 두면 MINIO_ENDPOINT 로 만든다 (예: http://localhost:29000)
    PUBLIC_UPLOAD_MAX_MB: int = 10
    PUBLIC_VIDEO_MAX_MB: int = 100
    # 동영상 생성(generate_video): Google Gemini Omni (Interactions API, GOOGLE_API_KEY 사용). 영상은 이미지와 같은 공개 버킷에 올린다
    VIDEO_GENERATION_ENABLED: bool = True
    VIDEO_API_KEY: str = ""  # 영상 전용 Gemini API 키. 비워 두면 GOOGLE_API_KEY 를 쓴다
    VIDEO_MODEL: str = "gemini-omni-1.1-flash"  # 모델 ID 는 바뀔 수 있어 설정으로 둔다
    VIDEO_RESOLUTION: str = "360p"  # 360p | 720p | 1080p | 4k. 360p 는 초안용 저가 단계(720p 의 약 1/3 단가)
    VIDEO_ASPECT_RATIO: str = "16:9"  # 16:9(가로) | 9:16(세로 숏폼)
    VIDEO_DEFAULT_SECONDS: int = 6  # 4/6/8/10 중 하나로 보정된다
    VIDEO_STRIP_AUDIO: bool = False  # true 면 ffmpeg 로 오디오 트랙을 제거한다 (ffmpeg 가 없으면 원본 사용)
    VIDEO_DAILY_LIMIT: int = 5  # 사용자당 하루 생성 한도 (0 이면 제한 없음, 서버 재시작 시 초기화). 영상은 비용이 크다
    VIDEO_TIMEOUT_SECONDS: int = 900
    # 토큰 사용량의 예상 비용 계산용 추가·덮어쓸 모델 단가(JSON): {"모델": [입력, 캐시 입력 또는 null, 출력]} (USD/1M tokens). 기본 표는 services/pricing.py
    MODEL_PRICES_JSON: str = ""
    SANDBOX_MAX_RUNNING_PER_USER: int = 5  # 한 사용자가 동시에 실행할 수 있는 sandbox 수 (넘으면 가장 오래 쓰지 않은 것을 백업 후 종료)
    SANDBOX_IDLE_MINUTES: int = 5  # last_used_at 기준 미사용 시간이 지나면 백업 후 종료
    SANDBOX_REAPER_INTERVAL_SECONDS: int = 60
    SANDBOX_BACKUP_MAX_MB: int = 1024  # 초과하면 백업 실패 처리 (sandbox 는 종료하지 않음)

    # 웹앱 배포(deploy_web_app): 불변 아카이브 + 앱 전용 경량 컨테이너 + 20000번대 프록시 포트 (요청 시 깨우기)
    APP_HOST_ENABLED: bool = True
    APP_PORT_START: int = 20000
    APP_PORT_END: int = 20099  # 포함. 비공개 앱(소유자 전용)이 쓰는 포트 범위
    APP_PUBLIC_PORT: int = 20100  # 공개 앱(App Store) 게이트웨이 포트: Host 헤더({slug}.APP_PUBLIC_DOMAIN)로 앱을 구분한다
    APP_PUBLIC_DOMAIN: str = "localhost"  # 공개 앱 호스트명의 도메인. 로컬은 *.localhost 가 브라우저에서 127.0.0.1 로 풀린다. 운영은 와일드카드 DNS(*.apps.example.com)
    APP_PUBLIC_SCHEME: str = "http"
    APP_PUBLIC_BIND: str = ""  # 공개 게이트웨이 바인드 주소 (비우면 APP_BIND_HOST)
    APP_MAX_RUNNING: int = 20  # 동시에 실행 중인 앱 컨테이너 전체 상한 (넘으면 가장 오래 쓰지 않은 앱을 내린다)
    APP_PUBLIC_RATE_PER_MIN: int = 600  # 공개 앱: IP·앱별 분당 요청 상한
    APP_PUBLIC_WAKE_PER_MIN: int = 6  # 공개 앱: 앱별 분당 깨우기 시도 상한 (익명 요청이 컨테이너를 계속 만들지 못하게)
    APP_REPORT_SUSPEND_THRESHOLD: int = 3  # 서로 다른 사용자 신고가 이 수에 이르면 자동 정지(검수 대기)
    APP_REVIEW_OPEN_TO_ALL: bool = True  # true: 사용자 역할이 생기기 전까지 로그인한 모든 사용자가 App Store 검수(승인·반려·정지)를 할 수 있다. false 면 ADMIN_EMAILS 만
    APP_REVIEW_ALLOW_SELF: bool = True  # false 면 자기 앱은 승인·반려할 수 없다 (역할을 도입하면 false 권장)
    ADMIN_EMAILS: str = ""  # 쉼표로 구분한 관리자 이메일 (App Store 검수·정지 권한)
    APP_BIND_HOST: str = "127.0.0.1"  # 프록시 리스너 바인드 주소. 원격 서버에서 외부에 열려면 0.0.0.0 (+ 방화벽, APP_REQUIRE_TOKEN)
    APP_PUBLIC_HOST: str = "localhost"  # 앱 URL 에 쓰는 호스트명
    APP_REQUIRE_TOKEN: bool = False  # true 면 새 앱은 접근 토큰이 필수 (배포 때 private 로 앱별 지정도 가능)
    APP_CONTAINER_PORT: int = 5173  # 앱이 컨테이너 안에서 듣는 포트 (환경변수 PORT 로 전달)
    APP_MAX_PER_USER: int = 10  # 사용자당 My Apps 에 둘 수 있는 앱 수 (시작에 실패한 앱도 센다). .env 의 APP_MAX_PER_USER 로 바꾼다
    APP_ARTIFACT_MAX_MB: int = 200
    APP_ARTIFACT_MAX_FILES: int = 50000
    APP_DATA_DIR: str = str(Path(__file__).parent.parent.parent / "data" / "apps")  # 아카이브·앱별 데이터(/workspace/data)
    APP_IDLE_MINUTES: int = 10  # 이 시간 동안 요청이 없으면 컨테이너를 내린다 (다음 요청에 다시 깨움)
    APP_STARTUP_TIMEOUT: int = 60
    APP_WAKE_WAIT_SECONDS: int = 25  # HTML 이 아닌 요청이 깨우는 동안 기다리는 시간
    APP_IMAGE: str = ""  # 비우면 SANDBOX_IMAGE
    APP_MEMORY_LIMIT: str = "512m"
    APP_CPU_LIMIT: float = 0.5
    APP_FAILURE_COOLDOWN: int = 30
    APP_MAX_RETRIES: int = 3

    # 파일 도구: 공개 다운로드 링크(publish_file/write_file) · URL 다운로드(download_file)
    PUBLIC_BASE_URL: str = "http://localhost:8500"  # 공개 링크에 붙는 백엔드 외부 접근 주소
    # Google Workspace 커넥터(Gmail·Calendar·Drive·Docs·Sheets·Slides): 사용자가 자기 Google 계정으로 OAuth 인증해 연결한다.
    # Google Cloud 콘솔에서 'OAuth 클라이언트 ID(웹 애플리케이션)'를 만들고 승인된 리디렉션 URI 에 GOOGLE_OAUTH_REDIRECT_URI 를 등록한다.
    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_OAUTH_CLIENT_SECRET: str = ""
    GOOGLE_OAUTH_REDIRECT_URI: str = ""  # 비우면 {PUBLIC_BASE_URL}/api/connectors/google/callback
    PUBLISH_DIR: str = str(Path(__file__).parent.parent.parent / "data" / "published")
    PUBLISH_EXPIRE_HOURS: int = 24
    PUBLISH_MAX_MB: int = 100
    DOWNLOAD_MAX_MB: int = 50

    # 브라우저 에이전트 (cli_browser_agent)
    BROWSER_MAX_STEPS: int = 30
    BROWSER_TIMEOUT_SECONDS: int = 300
    BROWSER_PARALLEL_MAX: int = 3  # 로컬 브라우저에서 동시에 열 수 있는 병렬 작업(탭) 수

    # 로컬 브라우저(데스크톱 앱의 내장 브라우저). CDP 주소가 있고 해당 사용자일 때만 sandbox 대신 사용한다.
    # 서버가 사용자 PC 에서 돌 때만 쓰는 설정이다 (원격 서버에서는 앱이 접속하는 브리지가 필요).
    LOCAL_BROWSER_CDP_URL: str = ""            # 예: http://127.0.0.1:9222 (비우면 사용 안 함)
    LOCAL_BROWSER_USER_ID: str = ""            # 이 사용자의 브라우저 작업만 로컬 브라우저로 보낸다 (필수)
    LOCAL_SHOTS_DIR: str = ""                   # 로컬 브라우저 스크린샷 저장 폴더 (비우면 시스템 임시 폴더)
    LOCAL_BROWSER_ALLOW_PRIVATE: bool = False  # 사설·루프백 주소 접속 허용 여부

    # 브라우저 에이전트 안전 정책
    # local: 로컬 브라우저(사용자 PC 세션)일 때만 쓰기 동작 승인 / all: sandbox 브라우저에도 적용 / off: 승인 없음
    BROWSER_BLOCK_PAYMENT: bool = True          # 결제·주문 확정 동작은 승인과 무관하게 실행하지 않는다 (결제 직전까지만 진행)
    BROWSER_APPROVAL_MODE: Literal["local", "all", "off"] = "local"
    BROWSER_APPROVAL_TIMEOUT_SECONDS: int = 300
    BROWSER_BLOCKED_DOMAINS: list[str] = []    # 이 도메인(하위 포함)으로는 이동하지 않는다
    BROWSER_ALLOWED_DOMAINS: list[str] = []    # 비어 있지 않으면 이 도메인만 허용
    BROWSER_SENSITIVE_DOMAINS: list[str] = []  # 추가로 '항상 승인' 대상으로 취급할 도메인 (기본 금융·결제 규칙 외)

    # 채팅 첨부 파일 업로드 (sandbox /workspace/uploads/)
    UPLOAD_MAX_MB: int = 50
    UPLOAD_FOLDER_MAX_FILES: int = 300  # 폴더 업로드: 최대 파일 수
    UPLOAD_FOLDER_MAX_MB: int = 100  # 폴더 업로드: 전체 크기
    REFERENCE_MAX_CHARS: int = 12000  # 참조(페이지·이전 대화) 하나당 에이전트에게 전달하는 최대 글자 수

    # 산출물(artifacts) 보기
    ARTIFACT_PREVIEW_MAX_KB: int = 200
    ARTIFACT_MAX_DOWNLOAD_MB: int = 100
    ARTIFACT_VIDEO_PREVIEW_MAX_MB: int = 50  # 이보다 큰 영상은 미리보기 대신 다운로드
    ARTIFACT_LIST_LIMIT: int = 2000

    # Skills (사용자별 설치 경로: SKILLS_DIR/{user_id}/{skill_name})
    SKILLS_DIR: str = str(Path(__file__).parent.parent.parent / "data" / "skills")
    SKILL_MAX_DOWNLOAD_MB: int = 50
    SKILL_MAX_EXTRACT_MB: int = 20

    # Memory (장기/단기 메모리)
    ENABLE_FOLLOWUP_SUGGESTIONS: bool = True  # 답변 뒤에 이어서 물어볼 만한 질문 2개를 추천
    ENABLE_MEMORY_EXTRACTION: bool = True  # 대화에서 자동 메모리 추출
    ENABLE_CONVERSATION_SUMMARY: bool = True  # 컨텍스트 창에서 밀려난 오래된 메시지의 롤링 요약
    MEMORY_CONTEXT_LIMIT: int = 15  # Agent 프롬프트에 주입할 최대 메모리 개수
    SHORT_TERM_MEMORY_TTL: int = 604800  # 단기 메모리 유지 시간 (초, 기본 7일). 항목을 저장·갱신할 때마다 다시 시작한다

    # RAG (Retrieval-Augmented Generation)
    CHROMA_PERSIST_DIR: str = str(Path(__file__).parent.parent.parent / "data" / "chroma")
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    RAG_TOP_K: int = 5  # 검색 시 상위 K개 청크
    RAG_MAX_FILE_SIZE_MB: int = 50  # 문서 최대 크기

    # 예약 작업 (스케줄러)
    # 메신저 게이트웨이 (Telegram long polling)
    CHANNELS_ENABLED: bool = True
    CHANNEL_SYNC_SECONDS: int = 15  # 봇 등록·해제를 반영하는 주기
    CHANNEL_RUN_TIMEOUT_SECONDS: int = 600
    CHANNEL_QUEUE_MAX: int = 5  # 실행 중 대기할 수 있는 메시지 수
    CHANNEL_PAIR_TTL_SECONDS: int = 600
    CHANNEL_DAILY_MESSAGE_LIMIT: int = 200  # 사용자당 하루 처리 메시지 수
    # 위험 도구(코드 실행·파일 변경·MCP·브라우저)는 실행 전에 Telegram 버튼으로 승인받는다
    CHANNEL_ALLOW_MCP: bool = True
    CHANNEL_ALLOW_BROWSER: bool = True
    CHANNEL_APPROVAL_TIMEOUT_SECONDS: int = 600

    SCHEDULER_ENABLED: bool = True
    SCHEDULER_POLL_SECONDS: int = 30  # 실행 시각이 된 작업을 찾는 주기
    SCHEDULER_MAX_CONCURRENT: int = 3  # 동시에 실행할 예약 작업 수
    SCHEDULER_MISFIRE_GRACE_SECONDS: int = 3600  # 서버 중단 등으로 이 시간 넘게 늦으면 실행하지 않고 건너뜀
    SCHEDULER_RUN_TIMEOUT_SECONDS: int = 600  # 회차당 최대 실행 시간
    SCHEDULER_MAX_TASKS_PER_USER: int = 10
    SCHEDULER_MAX_CONSECUTIVE_FAILURES: int = 3  # 연속 실패 시 자동 일시중지
    SCHEDULER_MIN_INTERVAL_HOURS: int = 1  # '매 N시간' 반복의 최소 간격
    SCHEDULER_DEFAULT_TIMEZONE: str = "Asia/Seoul"

    # 음성 생성(generate_speech): OpenAI Realtime 모델로 텍스트를 읽어 sandbox 에 WAV 로 저장한다 (공개 업로드는 하지 않는다)
    SPEECH_GENERATION_ENABLED: bool = True  # OPENAI_API_KEY 가 있어야 실제로 켜진다
    SPEECH_PROVIDER: Literal["realtime", "speech_api"] = "realtime"  # speech_api(/v1/audio/speech)는 모델이 2027-01-06 에 종료되므로 임시 예비용이다
    OPENAI_SPEECH_MODEL: str = "gpt-realtime-2.1-mini"  # realtime 방식 모델
    OPENAI_SPEECH_API_MODEL: str = "gpt-4o-mini-tts"  # speech_api 방식 모델 (종료 예정)
    SPEECH_FORMAT: Literal["mp3", "wav"] = "mp3"  # 저장 형식 (mp3 는 ffmpeg 필요, 없으면 wav 로 대신 저장)
    SPEECH_DEFAULT_VOICE: str = "marin"  # 목소리를 고르지 않으면 이 목소리로 바로 만든다
    SPEECH_VOICES: str = "marin,cedar"  # 선택할 수 있는 목소리(쉼표 구분). realtime 이 받는 값: alloy ash ballad coral echo sage shimmer verse marin cedar
    SPEECH_MAX_CHARS: int = 3000  # 한 번에 읽을 수 있는 글자 수 (비용 상한)
    SPEECH_CHUNK_CHARS: int = 500  # 긴 글은 문장 경계에서 이만큼씩 나눠 읽는다 (모델이 중간에 바꾸는 일을 줄인다)
    SPEECH_PREVIEW_CHARS: int = 140  # 목소리 미리듣기에 쓰는 앞부분 글자 수
    SPEECH_DAILY_LIMIT: int = 30  # 사용자당 하루 생성 횟수 (0 이면 제한 없음, 서버 재시작 시 초기화)
    SPEECH_TIMEOUT_SECONDS: int = 120  # 한 덩어리를 만드는 최대 시간

    # Drive: 사용자별 개인 산출물 공간 (MinIO 비공개 버킷 + DB 폴더 트리). MINIO_ENDPOINT 등 인증은 위 MinIO 설정을 쓴다
    DRIVE_ENABLED: bool = True  # MinIO 가 설정되어 있어야 실제로 켜진다
    MINIO_DRIVE_BUCKET: str = "agent-drive"  # 비공개 버킷 (익명 정책을 걸지 않는다). 공개 버킷(MINIO_PUBLIC_BUCKET)과 섞지 말 것
    DRIVE_MAX_FILE_MB: int = 200
    DRIVE_QUOTA_GB: float = 5.0  # 사용자당 총량 (휴지통에 있는 파일도 영구 삭제 전까지 센다)
    DRIVE_MAX_DEPTH: int = 20
    DRIVE_MAX_CHILDREN: int = 10000  # 폴더 하나에 둘 수 있는 항목 수
    DRIVE_TRASH_RETENTION_DAYS: int = 30  # 휴지통 보관 일수 (0 이면 자동 영구 삭제 안 함)
    DRIVE_IMPORT_MAX_MB: int = 500  # sandbox 에서 Drive 로 한 번에 저장할 수 있는 총 크기 (폴더 포함)
    DRIVE_IMPORT_MAX_FILES: int = 2000  # 한 번에 저장할 수 있는 파일 수 (node_modules·.git 등은 제외하고 센다)
    DRIVE_LOAD_MAX_MB: int = 50  # Drive 파일을 sandbox 로 불러올 수 있는 최대 크기 (메모리를 거치므로 작게 둔다)
    DRIVE_UPLOADS_PER_MIN: int = 120  # 사용자당 분당 업로드 요청 수 (0 이면 제한 없음)
    DRIVE_AUTO_SAVE_DEFAULT: bool = False  # 에이전트 산출물 자동 저장의 기본값 (사용자가 바꿀 수 있게 되기 전까지는 항상 수동)

    # Functions (Lambda 형 실행): zip 패키지를 실행할 때마다 새 격리 컨테이너에서 돌리고 폐기한다. 꺼져 있는 것이 기본이다
    FUNCTION_ENABLED: bool = False
    FUNCTION_ALLOWED_EMAILS: str = ""  # 쉼표로 구분한 사용 허용 이메일. '*' 는 모든 로그인 사용자. 관리자(ADMIN_EMAILS)는 항상 허용
    FUNCTION_RUNTIME_IMAGE_PYTHON: str = "ai-agent-fn-python:latest"  # infra/functions/build.sh 로 만든다
    FUNCTION_RUNTIME_IMAGE_BUN: str = "ai-agent-fn-bun:latest"
    FUNCTION_ALLOW_NETWORK: bool = False  # 서버 전체 상한: false 면 함수의 allow_network 설정과 무관하게 항상 네트워크 차단
    FUNCTION_MAX_CONCURRENT_PER_USER: int = 3
    FUNCTION_MAX_CONCURRENT_GLOBAL: int = 20
    FUNCTION_QUEUE_MAX_PER_USER: int = 20
    FUNCTION_RUNS_PER_DAY_PER_USER: int = 500
    FUNCTION_PACKAGE_MAX_MB: int = 50  # zip 크기
    FUNCTION_UNPACKED_MAX_MB: int = 250  # 풀었을 때 총 크기 (압축 폭탄 방지)
    FUNCTION_PACKAGE_MAX_FILES: int = 10000
    FUNCTION_EVENT_MAX_KB: int = 256
    FUNCTION_RESULT_MAX_KB: int = 1024
    FUNCTION_LOG_MAX_KB: int = 1024
    FUNCTION_TIMEOUT_DEFAULT: int = 30
    FUNCTION_TIMEOUT_MAX: int = 900
    FUNCTION_MEMORY_DEFAULT_MB: int = 256
    FUNCTION_MEMORY_MAX_MB: int = 1024
    FUNCTION_SYNC_WAIT_SECONDS: int = 30  # 동기 실행이 결과를 기다리는 최대 시간. 넘으면 run_id 로 전환한다
    FUNCTION_RUN_RETENTION_DAYS: int = 30  # 실행 이력·로그 보존 일수 (0 이면 자동 삭제 안 함)
    FUNCTION_VERSIONS_MAX: int = 50  # 함수 하나에 둘 수 있는 버전 수
    FUNCTION_TRIGGERS_MAX_PER_USER: int = 20  # 사용자당 예약·웹훅 트리거 수
    FUNCTION_WEBHOOK_RATE_PER_MIN: int = 60  # 웹훅 호출 제한: 토큰당·IP 당 분당 (0 이면 제한 없음)

    # 대화 공유 (로그인 없이 읽는 링크)
    SHARE_EXPIRE_DAYS: int = 0  # 0 이면 해제할 때까지 유효. 양수면 공유(갱신)한 날부터 이 일수 뒤 링크가 끊긴다
    SHARE_MAX_MESSAGES: int = 500  # 한 번에 공유할 수 있는 최대 메시지 수 (최근 것부터)
    SHARE_RATE_PER_MIN: int = 60  # 공유 링크 조회 제한: IP 당 분당 (0 이면 제한 없음)

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:80",
    ]

    # 위키 지식 그래프: 저장·수정·병합한 문서를 백그라운드에서 자동으로 지식화(개체·관계 추출)
    WIKI_GRAPH_AUTO: bool = True

    class Config:
        env_file = str(_ENV_FILE)
        env_file_encoding = "utf-8"


settings = Settings()
