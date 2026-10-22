# AI Agent System Architecture
> Genspark / Manus 스타일 AI Agent 플랫폼

---

## 목차

1. [시스템 개요](#1-시스템-개요)
2. [기술 스택](#2-기술-스택)
3. [전체 아키텍처](#3-전체-아키텍처)
4. [디렉터리 구조](#4-디렉터리-구조)
5. [Backend 상세 설계](#5-backend-상세-설계)
6. [Frontend 상세 설계](#6-frontend-상세-설계)
7. [Agent 시스템 설계](#7-agent-시스템-설계)
8. [MCP 클라이언트 시스템](#8-mcp-클라이언트-시스템)
9. [Sandbox 격리 환경](#9-sandbox-격리-환경)
10. [데이터베이스 설계](#10-데이터베이스-설계)
11. [API 명세](#11-api-명세)
12. [WebSocket 프로토콜](#12-websocket-프로토콜)
13. [인프라 및 배포](#13-인프라-및-배포)
14. [보안 설계](#14-보안-설계)
15. [개발 로드맵](#15-개발-로드맵)

---

## 1. 시스템 개요

### 1.1 프로젝트 목표

Genspark, Manus와 동일한 수준의 AI Agent 플랫폼을 구축한다.
사용자는 채팅 인터페이스를 통해 복잡한 멀티스텝 태스크를 Agent에게 위임하고,
Agent는 MCP 도구, 웹 크롤링, 웹서치 등의 도구를 활용하여 자율적으로 작업을 수행한다.
모든 작업은 사용자별로 완전히 격리된 Sandbox 환경에서 실행된다.

### 1.2 핵심 기능

| 기능 | 설명 |
|------|------|
| Multi-step Agent 실행 | LangChain `create_react_agent` 기반 ReAct Loop |
| MCP 통합 | Web UI에서 MCP 서버 등록/관리, 동적 tool 로딩 |
| 웹 크롤링 | Playwright 기반 헤드리스 브라우저 크롤링 |
| 웹 서치 | Tavily / SerpAPI 통합 검색 도구 |
| 사용자 Sandbox | 사용자별 Docker 컨테이너 격리 환경 |
| 실시간 스트리밍 | Agent 사고 과정 및 결과 WebSocket 스트리밍 |
| 채팅 UI | ChatGPT / Genspark 스타일 채팅 인터페이스 |
| Agno 통합 | Agno 프레임워크 기반 멀티 에이전트 오케스트레이션 |

### 1.3 시스템 특징

- **Agno + LangChain 하이브리드**: Agno의 멀티에이전트 오케스트레이션과 LangChain의 `create_react_agent` 결합
- **동적 MCP 등록**: 런타임에 MCP 서버를 등록하고 tool로 즉시 활용
- **스트리밍 사고 과정**: Agent의 Thought → Action → Observation 과정을 실시간으로 사용자에게 전달
- **사용자별 완전 격리**: 각 사용자의 작업이 독립된 컨테이너 내에서 실행

---

## 2. 기술 스택

### 2.1 Backend

```
언어          : Python 3.12+
패키지 관리   : uv
웹 프레임워크 : FastAPI 0.115+
ASGI 서버     : Uvicorn + Gunicorn
Agent 프레임워크:
  - Agno (agno-agi)         → 멀티에이전트 오케스트레이션
  - LangChain 0.3+          → create_react_agent, Tool 추상화
  - LangGraph 0.2+          → Agent State Machine
MCP 클라이언트: mcp (python-sdk)
LLM 통합      :
  - Anthropic Claude        → 기본 LLM
  - OpenAI GPT-4o           → 보조 LLM
  - Google Gemini           → 보조 LLM
크롤링        : Playwright (async)
데이터베이스  : PostgreSQL 16 (주), Redis 7 (캐시/세션/큐)
ORM           : SQLAlchemy 2.0 (async)
마이그레이션  : Alembic
인증          : JWT (python-jose)
태스크 큐     : Celery + Redis
컨테이너      : Docker SDK for Python
```

### 2.2 Frontend

```
언어          : TypeScript 5+
프레임워크    : React 19 + Vite 6
상태관리      : Zustand + TanStack Query v5
스타일        : Tailwind CSS v4 + shadcn/ui
실시간 통신   : WebSocket (native) + EventSource (SSE fallback)
마크다운 렌더링: react-markdown + rehype-highlight
코드 하이라이팅: Shiki
아이콘        : Lucide React
라우팅        : React Router v7
폼            : React Hook Form + Zod
```

### 2.3 인프라

```
컨테이너화    : Docker + Docker Compose
오케스트레이션: Kubernetes (prod) / Docker Compose (dev)
역방향 프록시  : Nginx
모니터링      : Prometheus + Grafana
로깅          : Loki + Promtail
CI/CD         : GitHub Actions
```

---

## 3. 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client (Browser)                          │
│                    React + TypeScript SPA                        │
│         Chat UI │ MCP Config UI │ Sandbox Manager UI            │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS / WebSocket
┌────────────────────────────▼────────────────────────────────────┐
│                        Nginx (Reverse Proxy)                     │
│              SSL Termination │ Load Balancing │ Static Serve     │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                    FastAPI Application Server                     │
│                                                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │  Auth API   │  │   Chat API   │  │     MCP Config API     │  │
│  │  /auth/*    │  │  /chat/*     │  │     /mcp/*             │  │
│  └─────────────┘  └──────┬───────┘  └──────────┬─────────────┘  │
│                          │                      │                 │
│  ┌───────────────────────▼──────────────────────▼─────────────┐  │
│  │               Agent Orchestration Layer                      │  │
│  │                                                              │  │
│  │  ┌─────────────────┐    ┌──────────────────────────────┐   │  │
│  │  │  Agno Framework │    │  LangChain create_react_agent │   │  │
│  │  │  (Multi-Agent)  │◄──►│  (ReAct Loop Execution)      │   │  │
│  │  └────────┬────────┘    └──────────────┬───────────────┘   │  │
│  │           │                             │                    │  │
│  │  ┌────────▼─────────────────────────────▼───────────────┐  │  │
│  │  │                    Tool Registry                       │  │  │
│  │  │                                                        │  │  │
│  │  │  ┌──────────┐  ┌──────────┐  ┌────────────────────┐  │  │  │
│  │  │  │ MCP Tools│  │Web Search│  │  Crawler Tool      │  │  │  │
│  │  │  │(Dynamic) │  │(Tavily)  │  │  (Playwright)      │  │  │  │
│  │  │  └────┬─────┘  └──────────┘  └────────────────────┘  │  │  │
│  │  └───────┼────────────────────────────────────────────────┘  │  │
│  └──────────┼─────────────────────────────────────────────────┘  │
│             │                                                      │
└─────────────┼──────────────────────────────────────────────────┘
              │
┌─────────────▼──────────────────────────────────────────────────┐
│                    MCP Client Manager                            │
│                                                                   │
│  User A MCP Session ──► [stdio MCP Server] [SSE MCP Server]     │
│  User B MCP Session ──► [Custom MCP Server]                     │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                   User Sandbox Pool                               │
│                                                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  Sandbox: User A │  │  Sandbox: User B │  │  Sandbox: User C │  │
│  │  Docker Container│  │  Docker Container│  │  Docker Container│  │
│  │  - File System   │  │  - File System   │  │  - File System   │  │
│  │  - Python Env    │  │  - Python Env    │  │  - Python Env    │  │
│  │  - Playwright    │  │  - Playwright    │  │  - Playwright    │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                    Data Layer                                     │
│                                                                   │
│  ┌─────────────────────┐      ┌──────────────────────────────┐  │
│  │   PostgreSQL 16      │      │         Redis 7               │  │
│  │  - users             │      │  - session store              │  │
│  │  - conversations     │      │  - agent state cache          │  │
│  │  - messages          │      │  - celery broker              │  │
│  │  - mcp_configs       │      │  - websocket pub/sub          │  │
│  │  - tool_executions   │      │  - rate limiting              │  │
│  └─────────────────────┘      └──────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. 디렉터리 구조

```
ai-agent-platform/
│
├── pyproject.toml                  # uv 루트 워크스페이스 설정
├── uv.lock
├── .env.example
├── docker-compose.yml
├── docker-compose.prod.yml
├── Makefile
├── CLAUDE.md                       # 이 파일
│
├── backend/                        # FastAPI Backend
│   ├── pyproject.toml
│   ├── Dockerfile
│   │
│   ├── app/
│   │   ├── main.py                 # FastAPI 앱 진입점
│   │   ├── config.py               # 환경 변수 / 설정
│   │   ├── dependencies.py         # FastAPI 의존성 주입
│   │   │
│   │   ├── api/                    # API 라우터
│   │   │   ├── __init__.py
│   │   │   ├── auth.py             # 인증 (로그인, 회원가입, JWT)
│   │   │   ├── chat.py             # 채팅 (세션, 메시지, 스트리밍)
│   │   │   ├── mcp.py              # MCP 설정 CRUD
│   │   │   ├── sandbox.py          # Sandbox 관리
│   │   │   ├── tools.py            # Tool 목록/실행 이력
│   │   │   └── ws.py               # WebSocket 엔드포인트
│   │   │
│   │   ├── agent/                  # Agent 핵심 로직
│   │   │   ├── __init__.py
│   │   │   ├── orchestrator.py     # Agno 기반 멀티에이전트 오케스트레이터
│   │   │   ├── react_agent.py      # LangChain create_react_agent 래퍼
│   │   │   ├── streaming.py        # Agent 스트리밍 핸들러
│   │   │   ├── state.py            # Agent State 정의 (LangGraph)
│   │   │   ├── prompts/            # 모든 프롬프트(.md)와 로더 (prompts/README.md 참고)
│   │   │   └── memory.py           # 대화 메모리 관리
│   │   │
│   │   ├── mcp/                    # MCP 클라이언트
│   │   │   ├── __init__.py
│   │   │   ├── client.py           # MCPClient 핵심 구현
│   │   │   ├── manager.py          # 사용자별 MCP 세션 관리
│   │   │   ├── tool_adapter.py     # MCP Tool → LangChain Tool 변환
│   │   │   ├── transport.py        # stdio / SSE / WebSocket 전송 추상화
│   │   │   └── registry.py         # Tool 레지스트리
│   │   │
│   │   ├── tools/                  # Agent 내장 도구
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # BaseTool 추상 클래스
│   │   │   ├── web_search.py       # Tavily / SerpAPI 웹서치
│   │   │   ├── crawler.py          # Playwright 크롤러
│   │   │   ├── code_executor.py    # Sandbox 내 코드 실행
│   │   │   ├── file_manager.py     # Sandbox 파일 시스템 조작
│   │   │   └── memory_tool.py      # 장기 기억 저장/검색
│   │   │
│   │   ├── sandbox/                # Sandbox 관리
│   │   │   ├── __init__.py
│   │   │   ├── manager.py          # Docker 컨테이너 생명주기
│   │   │   ├── executor.py         # 컨테이너 내 명령 실행
│   │   │   └── pool.py             # 컨테이너 풀 관리
│   │   │
│   │   ├── models/                 # DB 모델 (SQLAlchemy)
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── conversation.py
│   │   │   ├── message.py
│   │   │   ├── mcp_config.py
│   │   │   └── tool_execution.py
│   │   │
│   │   ├── schemas/                # Pydantic 스키마
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── chat.py
│   │   │   ├── mcp.py
│   │   │   └── agent.py
│   │   │
│   │   ├── services/               # 비즈니스 로직 서비스
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py
│   │   │   ├── chat_service.py
│   │   │   ├── mcp_service.py
│   │   │   └── sandbox_service.py
│   │   │
│   │   ├── db/                     # 데이터베이스
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # Base 선언
│   │   │   ├── session.py          # AsyncSession 팩토리
│   │   │   └── migrations/         # Alembic 마이그레이션
│   │   │
│   │   └── core/                   # 공통 유틸리티
│   │       ├── __init__.py
│   │       ├── security.py         # JWT, 비밀번호 해싱
│   │       ├── websocket.py        # WebSocket 연결 관리자
│   │       ├── events.py           # 이벤트 브로커 (Redis pub/sub)
│   │       └── exceptions.py       # 커스텀 예외
│   │
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── e2e/
│
├── frontend/                       # React Frontend
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── Dockerfile
│   │
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       │
│       ├── pages/                  # 페이지 컴포넌트
│       │   ├── AuthPage.tsx        # 로그인/회원가입
│       │   ├── ChatPage.tsx        # 메인 채팅 페이지
│       │   ├── McpSettingsPage.tsx # MCP 설정 페이지
│       │   └── SandboxPage.tsx     # Sandbox 모니터링
│       │
│       ├── components/
│       │   ├── chat/
│       │   │   ├── ChatLayout.tsx          # 전체 레이아웃
│       │   │   ├── Sidebar.tsx             # 대화 목록 사이드바
│       │   │   ├── MessageList.tsx         # 메시지 목록
│       │   │   ├── MessageBubble.tsx       # 개별 메시지
│       │   │   ├── AgentThinkingPanel.tsx  # Thought/Action/Obs 표시
│       │   │   ├── InputBar.tsx            # 메시지 입력창
│       │   │   ├── ToolCallCard.tsx        # Tool 호출 카드
│       │   │   └── StreamingCursor.tsx     # 스트리밍 커서
│       │   │
│       │   ├── mcp/
│       │   │   ├── McpServerList.tsx       # MCP 서버 목록
│       │   │   ├── McpServerForm.tsx       # MCP 서버 등록/수정 폼
│       │   │   ├── McpToolViewer.tsx       # 연결된 Tool 목록
│       │   │   └── McpStatusBadge.tsx      # 연결 상태 배지
│       │   │
│       │   ├── sandbox/
│       │   │   ├── SandboxStatus.tsx       # Sandbox 상태 표시
│       │   │   ├── FileExplorer.tsx        # 파일 탐색기
│       │   │   └── Terminal.tsx            # 웹 터미널
│       │   │
│       │   └── ui/                         # shadcn/ui 공통 컴포넌트
│       │
│       ├── store/                  # Zustand 스토어
│       │   ├── authStore.ts
│       │   ├── chatStore.ts
│       │   ├── agentStore.ts
│       │   └── mcpStore.ts
│       │
│       ├── hooks/                  # 커스텀 훅
│       │   ├── useWebSocket.ts     # WebSocket 연결 훅
│       │   ├── useAgentStream.ts   # Agent 스트리밍 훅
│       │   └── useMcpConfig.ts     # MCP 설정 훅
│       │
│       ├── api/                    # API 클라이언트
│       │   ├── client.ts           # Axios 인스턴스
│       │   ├── auth.ts
│       │   ├── chat.ts
│       │   └── mcp.ts
│       │
│       └── types/                  # TypeScript 타입 정의
│           ├── agent.ts
│           ├── chat.ts
│           └── mcp.ts
│
├── sandbox-image/                  # 사용자 Sandbox Docker 이미지
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── entrypoint.sh
│
└── infra/
    ├── nginx/
    │   └── nginx.conf
    ├── k8s/
    │   ├── deployment.yaml
    │   └── service.yaml
    └── monitoring/
        ├── prometheus.yml
        └── grafana/
```

---

## 5. Backend 상세 설계

### 5.1 FastAPI 앱 진입점 (`app/main.py`)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, chat, mcp, sandbox, ws
from app.db.session import init_db
from app.mcp.manager import MCPSessionManager
from app.sandbox.pool import SandboxPool
from app.core.websocket import WebSocketManager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시 초기화
    await init_db()
    await MCPSessionManager.initialize()
    await SandboxPool.initialize(min_size=3, max_size=50)
    yield
    # 종료 시 정리
    await MCPSessionManager.cleanup()
    await SandboxPool.cleanup()

app = FastAPI(
    title="AI Agent Platform",
    lifespan=lifespan
)

# 라우터 등록
app.include_router(auth.router, prefix="/api/auth")
app.include_router(chat.router, prefix="/api/chat")
app.include_router(mcp.router, prefix="/api/mcp")
app.include_router(sandbox.router, prefix="/api/sandbox")
app.include_router(ws.router, prefix="/ws")
```

### 5.2 설정 관리 (`app/config.py`)

```python
from pydantic_settings import BaseSettings
from typing import Literal

class Settings(BaseSettings):
    # App
    APP_ENV: Literal["development", "production"] = "development"
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # Database
    DATABASE_URL: str  # postgresql+asyncpg://...
    REDIS_URL: str     # redis://...

    # LLM Providers
    ANTHROPIC_API_KEY: str
    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    DEFAULT_LLM_PROVIDER: Literal["anthropic", "openai", "google"] = "anthropic"
    DEFAULT_MODEL: str = "claude-opus-4-5"

    # Agent
    AGENT_MAX_ITERATIONS: int = 25
    AGENT_TIMEOUT_SECONDS: int = 300
    AGENT_MEMORY_WINDOW: int = 20

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

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## 6. Frontend 상세 설계

### 6.1 채팅 UI 구성

ChatGPT / Genspark / Manus 스타일의 3단 레이아웃:

```
┌────────────────────────────────────────────────────────────────┐
│  [Logo]   AI Agent Platform          [User] [Settings]         │  ← 상단 헤더
├──────────────┬─────────────────────────────────────────────────┤
│              │                                                   │
│  Sidebar     │         Chat Area (Main)                         │
│              │                                                   │
│  [+ New Chat]│  ┌──────────────────────────────────────────┐   │
│              │  │  Message: User                            │   │
│  ─────────── │  │  "파이썬으로 주식 분석해줘"                 │   │
│  Today       │  └──────────────────────────────────────────┘   │
│  > Chat 1    │                                                   │
│  > Chat 2    │  ┌──────────────────────────────────────────┐   │
│              │  │  Agent Thinking Panel (Collapsible)       │   │
│  Yesterday   │  │  ┌─────────────────────────────────────┐ │   │
│  > Chat 3    │  │  │ 🤔 Thought: 주식 데이터 검색 필요...  │ │   │
│              │  │  │ 🔧 Action: web_search("AAPL stock")  │ │   │
│              │  │  │ 👁 Observation: {"price": 189.5...}  │ │   │
│              │  │  └─────────────────────────────────────┘ │   │
│              │  └──────────────────────────────────────────┘   │
│              │                                                   │
│              │  ┌──────────────────────────────────────────┐   │
│              │  │  Message: Assistant                       │   │
│              │  │  AAPL 현재가는 $189.50...                  │   │
│              │  └──────────────────────────────────────────┘   │
│              │                                                   │
│              │  ┌──────────────────────────────────────────┐   │
│              │  │ [📎] 메시지를 입력하세요...    [MCP] [전송] │   │
│              │  └──────────────────────────────────────────┘   │
│  [MCP 설정]  │                                                   │
│  [Sandbox]   │                                                   │
└──────────────┴─────────────────────────────────────────────────┘
```

### 6.2 MCP 설정 UI

```
┌──────────────────────────────────────────────────────────────┐
│  MCP 서버 설정                                    [+ 서버 추가] │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 🟢 filesystem-server          stdio         [편집][삭제] │  │
│  │    Tools: read_file, write_file, list_dir (3개)       │  │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 🟢 github-mcp                 SSE           [편집][삭제] │  │
│  │    Tools: create_issue, list_repos, get_pr (12개)    │  │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 🔴 custom-server              stdio         [편집][삭제] │  │
│  │    연결 실패: 서버를 시작할 수 없습니다                   │  │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  MCP 서버 추가                                                 │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ 이름: [filesystem-server        ]                        │ │
│  │ 전송: [stdio ▼]  [SSE]  [WebSocket]                     │ │
│  │ 명령어: [uvx mcp-server-filesystem /home/user/workspace] │ │
│  │ 환경변수:                                                 │ │
│  │ [+ 추가]  KEY=[        ]  VALUE=[              ]         │ │
│  │                               [취소] [저장 및 연결]       │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### 6.3 Agent Thinking Panel 상세

```typescript
// AgentThinkingPanel.tsx
interface AgentStep {
  type: "thought" | "action" | "observation" | "final";
  content: string;
  tool?: string;
  toolInput?: Record<string, unknown>;
  timestamp: string;
}

// 스트리밍으로 수신되는 이벤트 타입
type AgentStreamEvent =
  | { type: "thought"; content: string }
  | { type: "tool_call"; tool: string; input: unknown }
  | { type: "tool_result"; output: string; error?: string }
  | { type: "token"; content: string }         // 최종 응답 토큰
  | { type: "done"; message_id: string }
  | { type: "error"; message: string };
```

---

## 7. Agent 시스템 설계

### 7.1 Agno + LangChain 하이브리드 아키텍처

```
사용자 요청
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│              AgnoOrchestrator (오케스트레이터)                 │
│                                                               │
│  요청 분석 → 서브 에이전트 할당 → 결과 통합                     │
│                                                               │
│  ┌───────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ ResearchAgent │  │  CoderAgent  │  │  BrowserAgent    │  │
│  │ (검색/수집)   │  │  (코드 작성) │  │  (웹 자동화)     │  │
│  │               │  │              │  │                  │  │
│  │ create_react_ │  │ create_react_│  │  create_react_   │  │
│  │ agent()       │  │ agent()      │  │  agent()         │  │
│  └───────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 ReAct Agent 구현 (`app/agent/react_agent.py`)

```python
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import BaseTool
from langchain_anthropic import ChatAnthropic
from typing import AsyncIterator
import asyncio

class AgentRunner:
    """LangChain create_react_agent 기반 Agent 실행기"""

    def __init__(
        self,
        tools: list[BaseTool],
        llm_provider: str = "anthropic",
        model: str = "claude-opus-4-5",
        max_iterations: int = 25,
    ):
        self.llm = self._build_llm(llm_provider, model)
        self.tools = tools
        self.max_iterations = max_iterations

    def _build_llm(self, provider: str, model: str):
        if provider == "anthropic":
            return ChatAnthropic(model=model, streaming=True)
        elif provider == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=model, streaming=True)
        elif provider == "google":
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(model=model, streaming=True)
        raise ValueError(f"Unknown provider: {provider}")

    def build_executor(self, system_prompt: str) -> AgentExecutor:
        prompt = PromptTemplate.from_template(
            system_prompt + "\n\n" + REACT_TEMPLATE
        )
        agent = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt,
        )
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            max_iterations=self.max_iterations,
            verbose=True,
            return_intermediate_steps=True,
            handle_parsing_errors=True,
        )

    async def astream_events(
        self,
        executor: AgentExecutor,
        user_input: str,
        chat_history: list,
    ) -> AsyncIterator[dict]:
        """Agent 실행 스트리밍 이벤트 생성기"""
        async for event in executor.astream_events(
            {"input": user_input, "chat_history": chat_history},
            version="v2",
        ):
            event_name = event["name"]
            event_data = event.get("data", {})

            # LLM 사고 과정 토큰
            if event_name == "on_llm_stream":
                chunk = event_data.get("chunk")
                if chunk and hasattr(chunk, "content"):
                    yield {"type": "thought", "content": chunk.content}

            # Tool 호출 시작
            elif event_name == "on_tool_start":
                yield {
                    "type": "tool_call",
                    "tool": event_data.get("name"),
                    "input": event_data.get("input"),
                }

            # Tool 결과
            elif event_name == "on_tool_end":
                yield {
                    "type": "tool_result",
                    "tool": event_data.get("name"),
                    "output": str(event_data.get("output", "")),
                }

            # 최종 응답 토큰
            elif event_name == "on_chain_stream":
                output = event_data.get("chunk", {})
                if isinstance(output, dict) and "output" in output:
                    yield {"type": "token", "content": output["output"]}
```

### 7.3 Agno 오케스트레이터 (`app/agent/orchestrator.py`)

```python
from agno.agent import Agent as AgnoAgent
from agno.models.anthropic import Claude
from agno.team import Team
from app.agent.react_agent import AgentRunner
from app.mcp.manager import MCPSessionManager
from app.tools import get_builtin_tools

class AgentOrchestrator:
    """
    Agno 기반 멀티에이전트 오케스트레이터.
    복잡한 태스크를 분석하여 적절한 서브 에이전트에게 위임한다.
    """

    def __init__(self, user_id: str):
        self.user_id = user_id

    async def build_team(self, mcp_tools: list) -> Team:
        """사용자의 MCP 설정과 내장 도구를 기반으로 에이전트 팀 구성"""
        builtin_tools = await get_builtin_tools(self.user_id)
        all_tools = builtin_tools + mcp_tools

        research_agent = AgnoAgent(
            name="ResearchAgent",
            role="웹 검색 및 정보 수집 전문가",
            model=Claude(id="claude-opus-4-5"),
            tools=[t for t in all_tools if t.name in ["web_search", "web_crawler"]],
            instructions=["최신 정보를 검색하고 신뢰할 수 있는 출처에서 데이터를 수집합니다."],
        )

        coder_agent = AgnoAgent(
            name="CoderAgent",
            role="코드 작성 및 실행 전문가",
            model=Claude(id="claude-opus-4-5"),
            tools=[t for t in all_tools if t.name in ["code_executor", "file_manager"]],
            instructions=["Python, JavaScript 등 코드를 작성하고 Sandbox에서 안전하게 실행합니다."],
        )

        browser_agent = AgnoAgent(
            name="BrowserAgent",
            role="웹 브라우저 자동화 전문가",
            model=Claude(id="claude-opus-4-5"),
            tools=[t for t in all_tools if t.name in ["web_crawler", "screenshot"]],
            instructions=["웹사이트를 방문하고 필요한 정보를 추출하거나 작업을 자동화합니다."],
        )

        return Team(
            name="AgentTeam",
            mode="coordinate",            # Agno 코디네이터 모드
            model=Claude(id="claude-opus-4-5"),
            members=[research_agent, coder_agent, browser_agent],
            instructions=[
                "사용자의 요청을 분석하여 적절한 팀원에게 작업을 위임하세요.",
                "복잡한 태스크는 여러 팀원이 협력하여 완료하세요.",
            ],
        )

    async def run(self, user_input: str, conversation_id: str):
        """태스크 실행 및 스트리밍"""
        mcp_tools = await MCPSessionManager.get_tools(self.user_id)
        team = await self.build_team(mcp_tools)
        async for chunk in await team.arun(user_input, stream=True):
            yield chunk
```

### 7.4 프롬프트 설계 (`app/agent/prompts/`)

```python
REACT_TEMPLATE = """
Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought: {agent_scratchpad}
"""

SYSTEM_PROMPT = """당신은 사용자의 복잡한 작업을 수행하는 AI 에이전트입니다.
주어진 도구들을 활용하여 사용자의 요청을 정확하고 효율적으로 처리하세요.

현재 사용 가능한 도구:
- 웹 검색: 최신 정보 검색
- 웹 크롤러: 웹페이지 내용 추출
- 코드 실행기: Python 코드 실행 (격리된 Sandbox 환경)
- 파일 관리자: 파일 읽기/쓰기
- MCP 도구: 사용자가 등록한 외부 도구들

작업 수행 원칙:
1. 단계별로 명확하게 사고하세요 (Thought)
2. 적절한 도구를 선택하세요 (Action)
3. 결과를 분석하고 다음 단계를 결정하세요 (Observation)
4. 최종 답변은 명확하고 구체적으로 제시하세요
"""
```

---

## 8. MCP 클라이언트 시스템

### 8.1 MCP 클라이언트 핵심 구현 (`app/mcp/client.py`)

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.types import Tool, TextContent
from langchain_core.tools import StructuredTool
from pydantic import create_model
import asyncio
import json

class MCPClient:
    """
    단일 MCP 서버에 대한 클라이언트.
    stdio / SSE / WebSocket 전송을 지원한다.
    """

    def __init__(self, config: "MCPServerConfig"):
        self.config = config
        self.session: ClientSession | None = None
        self._tools: list[Tool] = []

    async def connect(self):
        """MCP 서버에 연결하고 Tool 목록을 로드"""
        transport = self.config.transport  # "stdio" | "sse" | "websocket"

        if transport == "stdio":
            server_params = StdioServerParameters(
                command=self.config.command,
                args=self.config.args,
                env=self.config.env,
            )
            self._cm = stdio_client(server_params)
        elif transport == "sse":
            self._cm = sse_client(self.config.url)
        else:
            raise ValueError(f"Unsupported transport: {transport}")

        read, write = await self._cm.__aenter__()
        self.session = ClientSession(read, write)
        await self.session.__aenter__()
        await self.session.initialize()

        # Tool 목록 조회
        result = await self.session.list_tools()
        self._tools = result.tools

    async def disconnect(self):
        if self.session:
            await self.session.__aexit__(None, None, None)
        if hasattr(self, "_cm"):
            await self._cm.__aexit__(None, None, None)

    async def call_tool(self, name: str, arguments: dict) -> str:
        """MCP Tool 호출"""
        if not self.session:
            raise RuntimeError("Not connected")
        result = await self.session.call_tool(name, arguments)
        outputs = []
        for content in result.content:
            if isinstance(content, TextContent):
                outputs.append(content.text)
        return "\n".join(outputs)

    def to_langchain_tools(self) -> list[StructuredTool]:
        """MCP Tool을 LangChain Tool로 변환"""
        lc_tools = []
        for tool in self._tools:
            tool_name = f"mcp_{self.config.name}_{tool.name}"

            # Pydantic 입력 스키마 동적 생성
            input_schema = tool.inputSchema or {}
            properties = input_schema.get("properties", {})
            required = input_schema.get("required", [])

            fields = {}
            for prop_name, prop_info in properties.items():
                field_type = self._json_type_to_python(prop_info.get("type", "string"))
                if prop_name in required:
                    fields[prop_name] = (field_type, ...)
                else:
                    fields[prop_name] = (field_type | None, None)

            ArgsSchema = create_model(f"{tool_name}_args", **fields)

            # 비동기 호출 함수 클로저
            def make_func(t_name: str):
                async def _call(**kwargs) -> str:
                    return await self.call_tool(t_name, kwargs)
                return _call

            lc_tool = StructuredTool(
                name=tool_name,
                description=tool.description or f"MCP tool: {tool.name}",
                args_schema=ArgsSchema,
                coroutine=make_func(tool.name),
            )
            lc_tools.append(lc_tool)

        return lc_tools

    @staticmethod
    def _json_type_to_python(json_type: str) -> type:
        mapping = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        return mapping.get(json_type, str)
```

### 8.2 MCP 세션 매니저 (`app/mcp/manager.py`)

```python
from app.mcp.client import MCPClient
from app.models.mcp_config import MCPServerConfig
from app.db.session import get_session
import asyncio
from typing import Dict

class MCPSessionManager:
    """
    사용자별 MCP 세션을 관리한다.
    각 사용자는 여러 개의 MCP 서버를 등록할 수 있으며,
    세션은 백그라운드에서 유지된다.
    """

    _sessions: Dict[str, Dict[str, MCPClient]] = {}
    # 구조: {user_id: {server_name: MCPClient}}

    @classmethod
    async def get_or_create_session(
        cls, user_id: str, config: MCPServerConfig
    ) -> MCPClient:
        user_sessions = cls._sessions.setdefault(user_id, {})
        if config.name not in user_sessions:
            client = MCPClient(config)
            await client.connect()
            user_sessions[config.name] = client
        return user_sessions[config.name]

    @classmethod
    async def get_tools(cls, user_id: str) -> list:
        """해당 사용자의 모든 MCP Tool을 LangChain Tool 형태로 반환"""
        from app.services.mcp_service import MCPService
        configs = await MCPService.get_user_configs(user_id)

        all_tools = []
        for config in configs:
            try:
                client = await cls.get_or_create_session(user_id, config)
                all_tools.extend(client.to_langchain_tools())
            except Exception as e:
                # 연결 실패한 서버는 건너뜀
                print(f"MCP connect failed [{config.name}]: {e}")

        return all_tools

    @classmethod
    async def reload_session(cls, user_id: str, server_name: str):
        """특정 MCP 서버 세션 재연결"""
        user_sessions = cls._sessions.get(user_id, {})
        if server_name in user_sessions:
            await user_sessions[server_name].disconnect()
            del user_sessions[server_name]

    @classmethod
    async def cleanup(cls):
        for user_sessions in cls._sessions.values():
            for client in user_sessions.values():
                await client.disconnect()
        cls._sessions.clear()
```

### 8.3 MCP 설정 DB 모델

```python
# app/models/mcp_config.py
from sqlalchemy import Column, String, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class MCPServerConfig(Base):
    __tablename__ = "mcp_configs"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)           # 서버 식별자
    display_name = Column(String, nullable=False)   # UI 표시명
    transport = Column(String, default="stdio")     # stdio | sse | websocket
    command = Column(String, nullable=True)         # stdio 전용: 실행 명령
    args = Column(JSON, default=list)               # stdio 전용: 명령 인자
    url = Column(String, nullable=True)             # SSE/WS 전용: 서버 URL
    env = Column(JSON, default=dict)                # 환경 변수
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

---

## 9. Sandbox 격리 환경

### 9.1 Sandbox 아키텍처

```
┌─────────────────────────────────────────────────────┐
│              Sandbox Pool Manager                    │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │  Warm Container Pool (미리 생성된 컨테이너)    │   │
│  │  [Container 1] [Container 2] [Container 3]   │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
│  사용자 요청 → 풀에서 컨테이너 할당 → 사용 후 반환    │
└─────────────────────────────────────────────────────┘

각 Sandbox 컨테이너:
┌───────────────────────────────────────────────┐
│  Docker Container (sandbox-image)              │
│                                               │
│  /workspace/          ← 사용자 작업 디렉터리   │
│  Python 3.12 (uv)     ← Python 실행 환경      │
│  Playwright           ← 브라우저 자동화        │
│  네트워크: 외부 HTTP(S)만 허용 (화이트리스트)   │
│  CPU: 1 core 제한                              │
│  Memory: 512MB 제한                            │
│  Disk: 1GB 제한                                │
└───────────────────────────────────────────────┘
```

### 9.2 Sandbox 매니저 (`app/sandbox/manager.py`)

```python
import docker
import asyncio
from typing import Optional

class SandboxManager:
    """사용자별 Docker Sandbox 컨테이너 관리"""

    def __init__(self):
        self.client = docker.from_env()

    async def create_sandbox(self, user_id: str) -> str:
        """새 Sandbox 컨테이너 생성, container_id 반환"""
        loop = asyncio.get_event_loop()
        container = await loop.run_in_executor(
            None,
            lambda: self.client.containers.run(
                image="ai-agent-sandbox:latest",
                name=f"sandbox-{user_id[:8]}",
                detach=True,
                remove=False,
                network=settings.SANDBOX_NETWORK,
                cpu_quota=100000,              # 1 CPU
                mem_limit=settings.SANDBOX_MEMORY_LIMIT,
                volumes={
                    f"/data/sandboxes/{user_id}": {
                        "bind": "/workspace",
                        "mode": "rw",
                    }
                },
                environment={
                    "USER_ID": user_id,
                    "HOME": "/workspace",
                },
                working_dir="/workspace",
                security_opt=["no-new-privileges"],
                cap_drop=["ALL"],
                read_only=False,
            )
        )
        return container.id

    async def exec_command(
        self,
        container_id: str,
        command: str,
        timeout: int = 30,
    ) -> tuple[int, str, str]:
        """컨테이너 내 명령 실행, (exit_code, stdout, stderr) 반환"""
        loop = asyncio.get_event_loop()
        container = self.client.containers.get(container_id)

        result = await loop.run_in_executor(
            None,
            lambda: container.exec_run(
                cmd=["bash", "-c", command],
                stdout=True,
                stderr=True,
                demux=True,
                timeout=timeout,
            )
        )
        exit_code = result.exit_code
        stdout = (result.output[0] or b"").decode()
        stderr = (result.output[1] or b"").decode()
        return exit_code, stdout, stderr

    async def destroy_sandbox(self, container_id: str):
        """컨테이너 중지 및 제거"""
        loop = asyncio.get_event_loop()
        container = self.client.containers.get(container_id)
        await loop.run_in_executor(None, lambda: container.stop(timeout=5))
        await loop.run_in_executor(None, container.remove)
```

### 9.3 Sandbox Docker 이미지 (`sandbox-image/Dockerfile`)

```dockerfile
FROM python:3.12-slim

# 시스템 의존성
RUN apt-get update && apt-get install -y \
    curl wget git bash \
    chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# uv 설치
RUN pip install uv

# Playwright 설치
RUN uv pip install --system playwright && \
    playwright install chromium

# 작업 디렉터리
WORKDIR /workspace
RUN chmod 777 /workspace

# 보안: root 대신 sandbox 유저
RUN useradd -m -u 1000 sandbox
USER sandbox

ENTRYPOINT ["tail", "-f", "/dev/null"]
```

---

## 10. 데이터베이스 설계

### 10.1 ERD

```
users
├── id (PK, UUID)
├── email (UNIQUE)
├── hashed_password
├── display_name
├── is_active
├── created_at
└── updated_at

conversations
├── id (PK, UUID)
├── user_id (FK → users.id)
├── title
├── llm_provider
├── model_name
├── created_at
└── updated_at

messages
├── id (PK, UUID)
├── conversation_id (FK → conversations.id)
├── role ('user' | 'assistant' | 'system')
├── content (TEXT)
├── agent_steps (JSON)       ← Thought/Action/Obs 배열
├── tool_calls (JSON)        ← 사용된 Tool 목록
├── created_at
└── metadata (JSON)

mcp_configs
├── id (PK, UUID)
├── user_id (FK → users.id)
├── name (server identifier)
├── display_name
├── transport ('stdio'|'sse'|'websocket')
├── command
├── args (JSON)
├── url
├── env (JSON)
├── is_active
└── created_at

tool_executions
├── id (PK, UUID)
├── message_id (FK → messages.id)
├── tool_name
├── tool_input (JSON)
├── tool_output (TEXT)
├── duration_ms
├── success
└── created_at

sandboxes
├── id (PK, UUID)
├── user_id (FK → users.id)
├── container_id
├── status ('running'|'stopped'|'error')
├── created_at
└── last_used_at
```

---

## 11. API 명세

### 11.1 인증 API

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/auth/register` | 회원가입 |
| POST | `/api/auth/login` | 로그인 → JWT 발급 |
| POST | `/api/auth/refresh` | 토큰 갱신 |
| GET | `/api/auth/me` | 현재 사용자 정보 |

### 11.2 채팅 API

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/chat/conversations` | 대화 목록 |
| POST | `/api/chat/conversations` | 새 대화 생성 |
| DELETE | `/api/chat/conversations/{id}` | 대화 삭제 |
| GET | `/api/chat/conversations/{id}/messages` | 메시지 목록 |
| POST | `/api/chat/conversations/{id}/messages` | 메시지 전송 (SSE 스트리밍) |

### 11.3 MCP API

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/mcp/configs` | MCP 서버 목록 |
| POST | `/api/mcp/configs` | MCP 서버 등록 |
| PUT | `/api/mcp/configs/{id}` | MCP 서버 수정 |
| DELETE | `/api/mcp/configs/{id}` | MCP 서버 삭제 |
| POST | `/api/mcp/configs/{id}/test` | 연결 테스트 |
| GET | `/api/mcp/configs/{id}/tools` | 연결된 Tool 목록 |
| POST | `/api/mcp/configs/{id}/reload` | 세션 재연결 |

### 11.4 Sandbox API

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/sandbox/status` | Sandbox 상태 |
| POST | `/api/sandbox/start` | Sandbox 시작 |
| POST | `/api/sandbox/stop` | Sandbox 중지 |
| GET | `/api/sandbox/files` | 파일 목록 |
| GET | `/api/sandbox/files/{path}` | 파일 내용 |

### 11.5 WebSocket API

```
WS /ws/chat/{conversation_id}

Client → Server:
{
  "type": "message",
  "content": "사용자 입력",
  "llm_provider": "anthropic",   // optional
  "model": "claude-opus-4-5"     // optional
}

Server → Client (스트리밍 이벤트):
{"type": "thought",      "content": "검색이 필요합니다..."}
{"type": "tool_call",    "tool": "web_search", "input": {"query": "..."}}
{"type": "tool_result",  "tool": "web_search", "output": "...", "success": true}
{"type": "token",        "content": "검색 결과에 따르면"}
{"type": "done",         "message_id": "uuid", "usage": {...}}
{"type": "error",        "message": "오류 메시지"}
```

---

## 12. WebSocket 프로토콜

### 12.1 연결 관리자 (`app/core/websocket.py`)

```python
from fastapi import WebSocket
from typing import Dict
import asyncio
import json

class WebSocketManager:
    """WebSocket 연결 풀 및 이벤트 브로드캐스트"""

    def __init__(self):
        # {conversation_id: [WebSocket, ...]}
        self._connections: Dict[str, list[WebSocket]] = {}

    async def connect(self, conversation_id: str, ws: WebSocket):
        await ws.accept()
        self._connections.setdefault(conversation_id, []).append(ws)

    async def disconnect(self, conversation_id: str, ws: WebSocket):
        conns = self._connections.get(conversation_id, [])
        if ws in conns:
            conns.remove(ws)

    async def send_event(self, conversation_id: str, event: dict):
        """특정 대화의 모든 연결에 이벤트 전송"""
        conns = self._connections.get(conversation_id, [])
        for ws in conns[:]:
            try:
                await ws.send_json(event)
            except Exception:
                conns.remove(ws)
```

### 12.2 WebSocket 엔드포인트 (`app/api/ws.py`)

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.core.websocket import WebSocketManager
from app.agent.orchestrator import AgentOrchestrator
from app.services.chat_service import ChatService

router = APIRouter()
ws_manager = WebSocketManager()

@router.websocket("/chat/{conversation_id}")
async def chat_websocket(
    conversation_id: str,
    websocket: WebSocket,
    current_user = Depends(get_ws_user),
):
    await ws_manager.connect(conversation_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()

            if data["type"] == "message":
                user_content = data["content"]

                # 사용자 메시지 저장
                user_msg = await ChatService.save_message(
                    conversation_id, "user", user_content
                )

                # Agent 실행 및 스트리밍
                orchestrator = AgentOrchestrator(current_user.id)
                full_response = ""
                agent_steps = []

                async for event in orchestrator.run(user_content, conversation_id):
                    await ws_manager.send_event(conversation_id, event)

                    # 이벤트 누적
                    if event["type"] == "token":
                        full_response += event["content"]
                    elif event["type"] in ("thought", "tool_call", "tool_result"):
                        agent_steps.append(event)

                # Assistant 메시지 저장
                await ChatService.save_message(
                    conversation_id, "assistant", full_response,
                    agent_steps=agent_steps
                )

                await ws_manager.send_event(conversation_id, {
                    "type": "done",
                    "message_id": str(user_msg.id),
                })

    except WebSocketDisconnect:
        await ws_manager.disconnect(conversation_id, websocket)
```

---

## 13. 인프라 및 배포

### 13.1 Docker Compose (개발)

```yaml
# docker-compose.yml
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: agent_platform
      POSTGRES_USER: agent
      POSTGRES_PASSWORD: secret
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  backend:
    build: ./backend
    command: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    volumes:
      - ./backend:/app
      - /var/run/docker.sock:/var/run/docker.sock  # Sandbox 제어
    environment:
      - DATABASE_URL=postgresql+asyncpg://agent:secret@postgres/agent_platform
      - REDIS_URL=redis://redis:6379
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis

  celery:
    build: ./backend
    command: celery -A app.celery worker --loglevel=info
    volumes:
      - ./backend:/app
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - DATABASE_URL=postgresql+asyncpg://agent:secret@postgres/agent_platform
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis

  frontend:
    build: ./frontend
    command: npm run dev -- --host
    volumes:
      - ./frontend:/app
      - /app/node_modules
    ports:
      - "5173:5173"

  nginx:
    image: nginx:alpine
    volumes:
      - ./infra/nginx/nginx.conf:/etc/nginx/nginx.conf
    ports:
      - "80:80"
    depends_on:
      - backend
      - frontend

  sandbox-network:
    driver: bridge
    internal: false

volumes:
  postgres_data:

networks:
  default:
    name: agent-platform-network
  sandbox-network:
    name: sandbox-network
```

### 13.2 uv 워크스페이스 설정

```toml
# pyproject.toml (루트)
[tool.uv.workspace]
members = ["backend"]

# backend/pyproject.toml
[project]
name = "ai-agent-backend"
version = "0.1.0"
requires-python = ">=3.12"

dependencies = [
  # Web
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "python-multipart>=0.0.9",

  # Agent Frameworks
  "agno>=1.0",
  "langchain>=0.3",
  "langchain-anthropic>=0.3",
  "langchain-openai>=0.2",
  "langchain-google-genai>=2.0",
  "langgraph>=0.2",

  # MCP
  "mcp>=1.0",

  # LLM Providers
  "anthropic>=0.40",
  "openai>=1.50",
  "google-generativeai>=0.8",

  # Database
  "sqlalchemy[asyncio]>=2.0",
  "asyncpg>=0.29",
  "alembic>=1.13",
  "redis[hiredis]>=5.0",

  # Auth
  "python-jose[cryptography]>=3.3",
  "passlib[bcrypt]>=1.7",

  # Tools
  "playwright>=1.47",
  "tavily-python>=0.3",
  "beautifulsoup4>=4.12",
  "httpx>=0.27",

  # Task Queue
  "celery>=5.4",
  "flower>=2.0",

  # Container
  "docker>=7.0",

  # Settings
  "pydantic-settings>=2.5",
]

[tool.uv]
dev-dependencies = [
  "pytest>=8",
  "pytest-asyncio>=0.24",
  "httpx>=0.27",
  "ruff>=0.6",
  "mypy>=1.11",
]
```

---

## 14. 보안 설계

### 14.1 인증 및 인가

- **JWT 기반 인증**: Access Token (1시간) + Refresh Token (7일)
- **토큰 저장**: HttpOnly Cookie (XSS 방어)
- **CORS**: 허용된 Origin만 설정
- **Rate Limiting**: 사용자별 API 호출 제한 (Redis 기반)

### 14.2 Sandbox 보안

```
컨테이너 보안 설정:
- security_opt: ["no-new-privileges"]  # 권한 상승 차단
- cap_drop: ["ALL"]                    # 모든 Linux 캐퍼빌리티 제거
- 네트워크: 화이트리스트 기반 외부 접근만 허용
- 파일 시스템: 사용자별 독립 디렉터리만 마운트
- CPU/Memory: 하드 리밋 설정
- 실행 시간: 최대 5분 타임아웃
```

### 14.3 MCP 보안

- MCP 서버 설정은 사용자별로 완전 격리
- 서버 명령어 화이트리스트 검증 (위험 명령 차단)
- MCP Tool 호출 결과 크기 제한 (1MB)
- 민감한 환경변수 암호화 저장 (Fernet)

### 14.4 입력 검증

- 모든 API 입력: Pydantic v2 스키마 검증
- SQL Injection: SQLAlchemy ORM 사용 (파라미터화 쿼리)
- XSS: React 기본 이스케이프 + DOMPurify
- SSRF: 크롤러 URL 화이트리스트/블랙리스트

---

## 15. 개발 로드맵

### Phase 1 - 기반 구축 (2주)

```
[ ] 프로젝트 초기화 (uv workspace, Docker Compose)
[ ] PostgreSQL + Redis 셋업
[ ] FastAPI 기본 구조 (인증, DB, 설정)
[ ] React + Vite 프론트엔드 초기화
[ ] JWT 인증 플로우 완성
[ ] 기본 채팅 UI 구현
```

### Phase 2 - Agent 코어 (2주)

```
[ ] LangChain create_react_agent 통합
[ ] Agno 멀티에이전트 오케스트레이터
[ ] WebSocket 스트리밍 파이프라인
[ ] Agent Thinking Panel UI
[ ] 내장 도구: web_search (Tavily), web_crawler (Playwright)
[ ] 대화 기록 저장 및 불러오기
```

### Phase 3 - MCP 통합 (1.5주)

```
[ ] MCPClient 구현 (stdio, SSE 전송)
[ ] MCPSessionManager 사용자별 세션 관리
[ ] MCP Tool → LangChain Tool 변환기
[ ] MCP 설정 CRUD API
[ ] MCP 설정 Web UI
[ ] MCP Tool 목록 및 상태 UI
```

### Phase 4 - Sandbox 환경 (1.5주)

```
[ ] Sandbox Docker 이미지 빌드
[ ] SandboxManager (컨테이너 생명주기)
[ ] SandboxPool (웜 풀 관리)
[ ] code_executor Tool 구현
[ ] file_manager Tool 구현
[ ] Sandbox 파일 탐색기 UI
[ ] Sandbox 상태 모니터링 UI
```

### Phase 5 - 완성 및 배포 (1주)

```
[ ] 성능 최적화 (커넥션 풀, 캐싱)
[ ] 에러 핸들링 고도화
[ ] 테스트 코드 작성 (unit, integration)
[ ] Nginx 설정
[ ] 모니터링 (Prometheus + Grafana)
[ ] 프로덕션 Docker Compose / K8s 배포
```

---

## 빠른 시작

```bash
# 저장소 클론
git clone https://github.com/your-org/ai-agent-platform
cd ai-agent-platform

# 환경 변수 설정
cp .env.example .env
# .env 파일에서 API 키 등 설정

# uv 의존성 설치
uv sync

# Docker 환경 실행
docker compose up -d postgres redis

# DB 마이그레이션
cd backend && uv run alembic upgrade head

# 백엔드 실행
uv run uvicorn app.main:app --reload

# 프론트엔드 실행 (별도 터미널)
cd frontend && npm install && npm run dev
```

---

*이 문서는 AI Agent Platform의 전체 아키텍처 및 구현 가이드입니다.*
*각 모듈의 상세 구현은 해당 소스 파일의 docstring 및 인라인 주석을 참조하세요.*