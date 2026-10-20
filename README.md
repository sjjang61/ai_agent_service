# AI Agent Platform

Genspark / Manus 스타일의 AI Agent 플랫폼. 사용자는 채팅 인터페이스를 통해 복잡한 멀티스텝 태스크를 Agent에게 위임하고, Agent는 MCP 도구·웹크롤링·웹서치 등을 활용하여 자율적으로 작업을 수행합니다.

---

## 목차

1. [시스템 아키텍처](#시스템-아키텍처)
2. [기술 스택](#기술-스택)
3. [디렉터리 구조](#디렉터리-구조)
4. [개발환경 설정](#개발환경-설정)
5. [실행 명령어](#실행-명령어)
6. [API 엔드포인트](#api-엔드포인트)
7. [WebSocket 프로토콜](#websocket-프로토콜)
8. [MCP 서버 연동](#mcp-서버-연동)
9. [환경 변수](#환경-변수)

---

## 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (React SPA)                   │
│         Chat UI │ MCP Config UI │ Sandbox UI            │
└─────────────────────────┬───────────────────────────────┘
                          │ HTTPS / WebSocket
┌─────────────────────────▼───────────────────────────────┐
│                  Nginx (Reverse Proxy :80)               │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│              FastAPI Application (:8500)                  │
│                                                           │
│  /api/auth   /api/chat   /api/mcp   /api/sandbox  /ws   │
│                          │                                │
│  ┌───────────────────────▼──────────────────────────┐   │
│  │            Agent Orchestrator                     │   │
│  │                                                   │   │
│  │   LangChain create_react_agent (ReAct Loop)      │   │
│  │   ┌──────────┐ ┌──────────┐ ┌────────────────┐  │   │
│  │   │web_search│ │ crawler  │ │ code_executor  │  │   │
│  │   │ (Tavily) │ │(Playwright│ │  (Sandbox)     │  │   │
│  │   └──────────┘ └──────────┘ └────────────────┘  │   │
│  │   ┌──────────┐ ┌──────────┐                      │   │
│  │   │file_mgr  │ │MCP Tools │  ← 동적 로딩         │   │
│  │   └──────────┘ └──────────┘                      │   │
│  └───────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
         │                              │
┌────────▼────────┐           ┌─────────▼────────┐
│  MCP Client     │           │  Sandbox Pool     │
│  Manager        │           │                   │
│  (per-user      │           │  Docker Container │
│   sessions)     │           │  per user         │
└─────────────────┘           └───────────────────┘
         │
┌────────▼──────────────────────────────────────────┐
│                   Data Layer                       │
│  PostgreSQL 16          Redis 7                   │
│  - users                - session / JWT cache     │
│  - conversations        - Celery broker           │
│  - messages             - WebSocket pub/sub       │
│  - mcp_configs                                    │
│  - tool_executions                                │
│  - sandboxes                                      │
└───────────────────────────────────────────────────┘
```

### 핵심 플로우

```
사용자 메시지 입력
       │
       ▼
FastAPI WebSocket / SSE
       │
       ▼
AgentOrchestrator
  ├── ConversationMemory 로드 (DB → LangChain messages)
  ├── MCP Tools 로드 (사용자 등록 서버 → LangChain StructuredTool)
  ├── Builtin Tools 로드 (web_search, crawler, code_executor, file_manager)
  └── AgentStreamingHandler
          │
          ▼
    LangChain create_react_agent (ReAct Loop)
          │
    Thought → Action → Observation → ... → Final Answer
          │
    astream_events() → 실시간 이벤트 스트리밍
          │
          ├── type: "thought"     → UI AgentThinkingPanel
          ├── type: "tool_call"   → UI ToolCallCard
          ├── type: "tool_result" → UI ToolCallCard
          └── type: "token"       → UI MessageBubble (스트리밍)
```

---

## 기술 스택

### Backend
| 항목 | 기술 |
|------|------|
| 언어 | Python 3.12+ |
| 패키지 관리 | uv |
| 웹 프레임워크 | FastAPI 0.115+ |
| Agent | LangChain 0.3+ (`create_react_agent`) |
| LLM | Anthropic Claude (기본), OpenAI, Google Gemini |
| MCP | python-sdk (`mcp>=1.0`) |
| 크롤링 | Playwright (async) |
| 웹서치 | Tavily |
| ORM | SQLAlchemy 2.0 (async) |
| DB | PostgreSQL 16 |
| Cache/Queue | Redis 7 |
| Task Queue | Celery 5 |
| 컨테이너 | Docker SDK for Python |
| 인증 | JWT (python-jose + passlib bcrypt) |

### Frontend
| 항목 | 기술 |
|------|------|
| 언어 | TypeScript 5+ |
| 프레임워크 | React 19 + Vite 6 |
| 상태관리 | Zustand 5 |
| 서버 상태 | TanStack Query v5 |
| 스타일 | Tailwind CSS v3 |
| 실시간 통신 | Fetch SSE (스트리밍) + WebSocket |
| 마크다운 | react-markdown |
| 아이콘 | Lucide React |
| 라우팅 | React Router v7 |
| 폼 | React Hook Form + Zod |

---

## 디렉터리 구조

```
ai_agent_service/
├── .env.example               # 환경 변수 템플릿
├── docker-compose.yml         # 개발 환경 전체 구성
├── Makefile                   # 편의 명령어 모음
├── pyproject.toml             # uv workspace 설정
│
├── backend/
│   ├── pyproject.toml         # Python 의존성
│   ├── alembic.ini            # DB 마이그레이션 설정
│   └── app/
│       ├── main.py            # FastAPI 앱 진입점
│       ├── config.py          # 환경 설정 (pydantic-settings)
│       ├── dependencies.py    # FastAPI DI (get_db, get_current_user)
│       │
│       ├── api/               # 라우터
│       │   ├── auth.py        # POST /register, /login, GET /me
│       │   ├── chat.py        # 대화 CRUD + SSE 스트리밍
│       │   ├── mcp.py         # MCP 서버 CRUD + 테스트
│       │   ├── sandbox.py     # Sandbox 시작/중지/파일
│       │   └── ws.py          # WebSocket /ws/chat/{id}
│       │
│       ├── agent/             # Agent 핵심
│       │   ├── orchestrator.py  # 도구 조합 → 스트리밍 실행
│       │   ├── react_agent.py   # LangChain create_react_agent 래퍼
│       │   ├── streaming.py     # astream_events 핸들러
│       │   ├── memory.py        # 대화 메모리 (sliding window)
│       │   └── prompts.py       # ReAct 프롬프트 템플릿
│       │
│       ├── mcp/               # MCP 클라이언트
│       │   ├── client.py      # MCPClient (stdio/SSE 전송)
│       │   └── manager.py     # 사용자별 세션 풀
│       │
│       ├── tools/             # 내장 도구
│       │   ├── web_search.py  # Tavily 웹서치
│       │   ├── crawler.py     # Playwright 크롤러
│       │   ├── code_executor.py  # Sandbox Python 실행
│       │   ├── file_manager.py   # Sandbox 파일 조작
│       │   └── memory_tool.py    # 장기 기억 저장/검색
│       │
│       ├── sandbox/           # Docker 격리 환경
│       │   ├── manager.py     # 컨테이너 생성/실행/제거
│       │   └── pool.py        # 컨테이너 풀
│       │
│       ├── models/            # SQLAlchemy ORM 모델
│       ├── schemas/           # Pydantic v2 스키마
│       ├── services/          # 비즈니스 로직
│       ├── core/              # 공통 유틸 (JWT, WebSocket, 이벤트)
│       └── db/                # DB 세션 + Alembic 마이그레이션
│
├── frontend/
│   ├── src/
│   │   ├── pages/             # AuthPage, ChatPage, McpSettingsPage, SandboxPage
│   │   ├── components/
│   │   │   ├── chat/          # ChatLayout, Sidebar, MessageBubble, InputBar, AgentThinkingPanel
│   │   │   ├── mcp/           # McpServerList, McpServerForm
│   │   │   └── sandbox/       # SandboxStatus, ArtifactsPanel (산출물 보기)
│   │   ├── store/             # Zustand stores (auth, chat, agent, mcp)
│   │   ├── hooks/             # useAgentStream, useWebSocket, useMcpConfig
│   │   ├── api/               # Axios 클라이언트 + 엔드포인트
│   │   └── types/             # TypeScript 타입 정의
│   └── ...config files
│
├── sandbox-image/             # 사용자 Sandbox Docker 이미지
│   └── Dockerfile
│
└── infra/
    ├── nginx/nginx.conf        # 리버스 프록시
    ├── k8s/                    # Kubernetes 매니페스트
    └── monitoring/             # Prometheus 설정
```

---

## 개발환경 설정

### 사전 요구사항

- **Python 3.12+**
- **Node.js 22+**
- **Docker Desktop** (Sandbox 기능 사용 시)
- **uv** 패키지 매니저

```bash
# uv 설치 (macOS/Linux)
curl -LsSf https://astral.sh/uv/install.sh | sh

# uv 설치 확인
uv --version
```

### 1. 저장소 준비

```bash
cd ai_agent_service

# 환경 변수 설정
cp .env.example .env
```

### 2. `.env` 파일 편집

```bash
# 필수 설정
SECRET_KEY=your-random-secret-key-here      # 임의의 긴 문자열
ANTHROPIC_API_KEY=sk-ant-...                # Anthropic API 키 (필수)

# 선택 설정
OPENAI_API_KEY=sk-...                       # OpenAI 사용 시
TAVILY_API_KEY=tvly-...                     # 웹서치 기능 사용 시
```

> **SECRET_KEY 생성:** `python -c "import secrets; print(secrets.token_hex(32))"`

### 3. 데이터베이스 & Redis 시작

```bash
docker compose up -d postgres redis

# 상태 확인
docker compose ps
```

### 4. Backend 설정

```bash
# 의존성 설치
uv sync --directory backend

# Playwright 브라우저 설치 (크롤러 기능)
uv run --directory backend playwright install chromium
```

### 5. Frontend 설정

```bash
cd frontend && npm install
```

---

## 실행 명령어

### 개발 서버 실행 (로컬)

```bash
# 터미널 1 — DB/Redis (이미 실행 중이면 생략)
docker compose up -d postgres redis

# 터미널 2 — Backend
uv run --directory backend uvicorn app.main:app --reload --host 0.0.0.0 --port 8500

# 터미널 3 — Frontend
cd frontend && npm run dev
```

브라우저에서 **http://localhost:5173** 접속

### Docker Compose 전체 실행

```bash
# 모든 서비스 빌드 및 시작
docker compose up --build

# 백그라운드 실행
docker compose up -d --build

# 로그 확인
docker compose logs -f backend
docker compose logs -f frontend

# 중지
docker compose down
```

### Makefile 단축 명령어

```bash
make dev          # DB/Redis 시작 + backend/frontend 개발서버
make up           # Docker Compose 전체 시작
make down         # 전체 중지
make build        # 이미지 빌드
make migrate      # DB 마이그레이션 실행
make logs         # 전체 로그 출력
make test         # 테스트 실행
make sandbox-build  # Sandbox Docker 이미지 빌드
make clean        # 컨테이너 및 볼륨 전체 삭제
```

### DB 마이그레이션

```bash
# 마이그레이션 실행 (테이블 생성/업데이트)
uv run --directory backend alembic upgrade head

# 새 마이그레이션 파일 생성
uv run --directory backend alembic revision --autogenerate -m "description"

# 마이그레이션 이력 확인
uv run --directory backend alembic history
```

> **참고:** 개발 환경에서는 `init_db()`가 FastAPI 시작 시 자동으로 테이블을 생성합니다 (`CREATE TABLE IF NOT EXISTS`).

### Sandbox 이미지 빌드

```bash
# Sandbox Docker 이미지 빌드 (코드 실행 기능 사용 시 필요)
docker build -t ai-agent-sandbox:latest ./sandbox-image/
```

### Celery Worker 실행 (별도 태스크 큐 사용 시)

```bash
uv run --directory backend celery -A app.celery_app worker --loglevel=info
```

---

## API 엔드포인트

### 인증

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/api/auth/register` | 회원가입 |
| `POST` | `/api/auth/login` | 로그인 → JWT 발급 |
| `GET`  | `/api/auth/me` | 내 정보 조회 |

```bash
# 회원가입
curl -X POST http://localhost:8500/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"pass1234","display_name":"Alice"}'

# 로그인
curl -X POST http://localhost:8500/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"pass1234"}'
```

### 채팅

| Method | Path | 설명 |
|--------|------|------|
| `GET`  | `/api/chat/conversations` | 대화 목록 |
| `POST` | `/api/chat/conversations` | 새 대화 생성 |
| `DELETE` | `/api/chat/conversations/{id}` | 대화 삭제 |
| `GET`  | `/api/chat/conversations/{id}/messages` | 메시지 목록 |
| `POST` | `/api/chat/conversations/{id}/messages` | 메시지 전송 (SSE 스트리밍) |
| `POST` | `/api/chat/conversations/{id}/cancel` | 실행 중인 에이전트 취소 (진행 중인 LLM 호출·도구 대기·sandbox 명령 중단, 부분 결과는 저장) |

### MCP 서버 관리

| Method | Path | 설명 |
|--------|------|------|
| `GET`  | `/api/mcp/configs` | 등록된 MCP 서버 목록 |
| `POST` | `/api/mcp/configs` | MCP 서버 등록 |
| `PUT`  | `/api/mcp/configs/{id}` | MCP 서버 수정 |
| `DELETE` | `/api/mcp/configs/{id}` | MCP 서버 삭제 |
| `POST` | `/api/mcp/configs/{id}/test` | 연결 테스트 |
| `GET`  | `/api/mcp/configs/{id}/tools` | 연결된 Tool 목록 |
| `POST` | `/api/mcp/configs/{id}/reload` | 세션 재연결 |

### Sandbox

| Method | Path | 설명 |
|--------|------|------|
| `GET`  | `/api/sandbox/status` | 상태 조회 |
| `POST` | `/api/sandbox/start` | 컨테이너 시작 |
| `POST` | `/api/sandbox/stop` | 컨테이너 중지 |
| `GET`  | `/api/sandbox/files` | 파일 목록 |
| `GET`  | `/api/sandbox/files/{path}` | 파일 내용 |
| `GET`  | `/api/sandbox/artifacts` | 산출물 목록 (크기·수정시각·종류, 최근 수정순). 중지된 sandbox 는 `restorable` 로 백업 복구 가능 여부 안내 |
| `GET`  | `/api/sandbox/artifacts/preview?path=` | 텍스트 미리보기 (앞 200KB) |
| `GET`  | `/api/sandbox/artifacts/raw?path=&download=` | 파일 원본 다운로드 / 이미지 인라인 미리보기 |
| `POST` | `/api/sandbox/artifacts/publish` | 파일을 공개 다운로드 링크로 발행 |
| `POST` | `/api/sandbox/uploads` | 채팅 첨부 파일을 sandbox `/workspace/uploads/` 에 업로드 (multipart, 파일당 `UPLOAD_MAX_MB`) |

### 예약 작업 API

프롬프트와 반복 일정을 저장해 두면 시각이 되었을 때 사용자 없이 에이전트가 실행하고, 결과를 전용 대화와 이력에 남깁니다.

**채팅으로 예약**: 채팅에서 "매일 아침 9시에 AI 뉴스 요약해줘"처럼 말하면 에이전트가 `manage_schedule` 도구로 예약을 만들고(조회·수정·일시중지·재개·삭제 포함) 말풍선에 예약 카드를 보여줍니다.
- 사용자의 브라우저 시간대를 기본값으로 쓰고, 시스템 프롬프트에 현재 시각을 알려 "10분 뒤" 같은 상대 표현을 해석합니다.
- 안전장치: 변경·삭제 호출은 사용자의 **마지막 메시지**에서 인용한 문구(`request_quote`)가 있어야 하고(과거 요청의 재실행 방지), 같은 이름·같은 내용의 최근 예약은 중복으로 거부합니다. 이 도구로는 MCP·브라우저 허용을 켤 수 없고(예약 화면에서 직접 설정), 예약 실행(headless) 안에서는 도구가 제공되지 않습니다.

| Method | Path | 설명 |
|--------|------|------|
| `GET` / `POST` | `/api/schedules` | 예약 작업 목록 / 생성 (한 번·N시간마다·매일·평일·매주·매월) |
| `GET` / `PUT` / `DELETE` | `/api/schedules/{id}` | 조회 / 수정(일정이 바뀌면 다음 실행 재계산) / 삭제 |
| `POST` | `/api/schedules/{id}/enabled` | 일시중지·재개 (재개 시 연속 실패 수 초기화) |
| `POST` | `/api/schedules/{id}/run` | 지금 실행 (예약 일정은 그대로) |
| `GET` | `/api/schedules/{id}/runs` | 실행 이력 |
| `GET` | `/api/schedules/unread-count` | 확인하지 않은 실행 결과 수 (아이콘 바의 파란 점) |
| `POST` | `/api/schedules/{id}/read`, `/api/schedules/runs/{run_id}/read` | 읽음 처리 (결과 대화를 열면 자동으로도 처리) |

---

## WebSocket 프로토콜

```
WS ws://localhost:8500/ws/chat/{conversation_id}?token=<JWT>
```

**Client → Server:**
```json
{
  "type": "message",
  "content": "AAPL 주식 분석해줘",
  "llm_provider": "anthropic",
  "model": "claude-opus-4-5"
}
```

**Server → Client (스트리밍 이벤트):**
```json
{"type": "thought",      "content": "주식 데이터를 검색해야겠다..."}
{"type": "tool_call",    "tool": "web_search", "input": {"query": "AAPL stock price"}}
{"type": "tool_result",  "tool": "web_search", "output": "...", "success": true}
{"type": "token",        "content": "AAPL의 현재가는 "}
{"type": "token",        "content": "$189.50입니다..."}
{"type": "done",         "message_id": "uuid-..."}
{"type": "error",        "message": "오류 메시지"}
```

---

## MCP 서버 연동

Web UI(`/mcp`)에서 MCP 서버를 등록하거나, API로 직접 등록합니다.

### stdio 방식 예시 (filesystem)

```bash
curl -X POST http://localhost:8500/api/mcp/configs \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "filesystem",
    "display_name": "Filesystem Server",
    "transport": "stdio",
    "command": "uvx",
    "args": ["mcp-server-filesystem", "/tmp/workspace"]
  }'
```

### SSE 방식 예시

```bash
curl -X POST http://localhost:8500/api/mcp/configs \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-server",
    "display_name": "My MCP Server",
    "transport": "sse",
    "url": "http://localhost:3001/sse"
  }'
```

등록된 MCP Tool은 Agent 실행 시 자동으로 LangChain `StructuredTool`로 변환되어 ReAct 루프에서 사용됩니다.

---

## 환경 변수

| 변수명 | 필수 | 기본값 | 설명 |
|--------|------|--------|------|
| `SECRET_KEY` | ✅ | - | JWT 서명 키 |
| `ANTHROPIC_API_KEY` | ✅ | - | Claude API 키 |
| `DATABASE_URL` | ✅ | `postgresql+asyncpg://...` | PostgreSQL 연결 URL |
| `REDIS_URL` | ✅ | `redis://localhost:6379` | Redis 연결 URL |
| `OPENAI_API_KEY` | ❌ | - | OpenAI 사용 시 |
| `GOOGLE_API_KEY` | ❌ | - | Gemini 사용 시 |
| `TAVILY_API_KEY` | ❌ | - | 웹서치 기능 |
| `LLM_TYPE` | ❌ | `pet` | 사용할 LLM: `pet` \| `openai` \| `gemini` \| `anthropic` |
| `AGENT_ENGINE` | ❌ | `agno` | `agno`(멀티에이전트 Team) \| `langgraph`(단일 ReAct 에이전트) |
| `MCP_TOOL_MODE` | ❌ | `lazy` | `lazy`(목록만 프롬프트, `load_mcp_tool`/`call_mcp_tool`/`run_mcp_code` 사용) \| `direct`(모든 MCP 도구 개별 등록) |
| `BROWSER_MAX_STEPS` / `BROWSER_TIMEOUT_SECONDS` | ❌ | `30` / `300` | `cli_browser_agent` 의 최대 조작 횟수 / 제한 시간(초) |
| `PUBLIC_BASE_URL` | ❌ | `http://localhost:8500` | `publish_file` 공개 링크에 붙는 백엔드 외부 주소 |
| `PUBLISH_EXPIRE_HOURS` / `PUBLISH_MAX_MB` / `DOWNLOAD_MAX_MB` | ❌ | `24` / `100` / `50` | 공개 링크 유효시간·최대 크기, `download_file` 최대 크기 |
| `UPLOAD_MAX_MB` | ❌ | `50` | 채팅 첨부 파일 1개당 최대 크기 |
| `SCHEDULER_ENABLED` | ❌ | `true` | 예약 작업 자동 실행 (끄면 '지금 실행'만 동작) |
| `SCHEDULER_POLL_SECONDS` / `SCHEDULER_MAX_CONCURRENT` | ❌ | `30` / `3` | 실행 시각 확인 주기(초) / 동시에 실행할 작업 수 |
| `SCHEDULER_MISFIRE_GRACE_SECONDS` | ❌ | `3600` | 서버 중단 등으로 이만큼 넘게 늦은 회차는 실행하지 않고 건너뜀 |
| `SCHEDULER_RUN_TIMEOUT_SECONDS` | ❌ | `600` | 회차당 최대 실행 시간 |
| `SCHEDULER_MAX_TASKS_PER_USER` / `SCHEDULER_MAX_CONSECUTIVE_FAILURES` | ❌ | `10` / `3` | 사용자당 작업 수 / 연속 실패 시 자동 일시중지 |
| `SCHEDULER_MIN_INTERVAL_HOURS` / `SCHEDULER_DEFAULT_TIMEZONE` | ❌ | `1` / `Asia/Seoul` | 'N시간마다' 최소 간격 / 기본 시간대 |
| `PET_STREAMING` | ❌ | `false` | PetAgent 가 SSE 스트리밍을 지원하면 `true` |
| `OPENAI_MODEL` / `GEMINI_MODEL` / `ANTHROPIC_MODEL` | ❌ | `gpt-4o` / `gemini-2.5-flash` / `claude-sonnet-4-5` | LLM_TYPE 별 모델 (pet 은 `PET_MODEL_ID`) |
| `MINIO_ENDPOINT` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | ❌ | (비활성) | Sandbox 백업용 MinIO. 비우면 자동 백업/종료 꺼짐 |
| `MINIO_BUCKET` | ❌ | `sandbox-sessions` | 백업 버킷 (`{세션id}/workspace.tar.gz`) |
| `SANDBOX_IDLE_MINUTES` | ❌ | `10` | 미사용 시간이 지나면 백업 후 sandbox 종료 |
| `SANDBOX_BACKUP_MAX_MB` | ❌ | `500` | `/workspace` 백업 크기 제한 |
| `AGENT_MAX_ITERATIONS` | ❌ | `25` | Agent 최대 반복 횟수 |
| `SANDBOX_IMAGE` | ❌ | `ai-agent-sandbox:latest` | Sandbox 이미지 이름 |
| `SANDBOX_MEMORY_LIMIT` | ❌ | `512m` | 컨테이너 메모리 제한 |
| `CRAWLER_HEADLESS` | ❌ | `true` | 헤드리스 브라우저 여부 |

---

## 트러블슈팅

**DB 연결 오류:**
```bash
docker compose up -d postgres
docker compose logs postgres
```

**Playwright 브라우저 없음:**
```bash
uv run --directory backend playwright install chromium --with-deps
```

**MCP 서버 연결 실패:**
- Web UI → MCP Settings → 해당 서버의 **테스트(↻)** 버튼으로 오류 메시지 확인
- `command` 경로와 인자가 올바른지 확인

**Sandbox 이미지 없음:**
```bash
make sandbox-build
# 또는
docker build -t ai-agent-sandbox:latest ./sandbox-image/
```
