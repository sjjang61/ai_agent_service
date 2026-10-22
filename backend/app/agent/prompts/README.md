# 프롬프트 관리

LLM 에 보내는 모든 프롬프트는 이 폴더의 `.md` 파일입니다. 문구를 바꾸려면 해당 파일만 고치고 서버를 다시 시작하세요
(파일은 처음 읽을 때 캐시됩니다). 로더는 [`__init__.py`](__init__.py) 입니다.

## 문법
- 값이 들어갈 자리는 `{{이름}}` 입니다. 코드가 넘기는 값과 파일의 자리가 정확히 같아야 하며, 다르면 예외가 납니다.
- JSON 예시의 `{ }` 는 그대로 써도 됩니다.
- `---` 만 있는 줄은 문단 구분선입니다 (팀 지침처럼 여러 문단 목록인 파일). 서브에이전트 파일은 첫 문단이 역할, 나머지가 지침입니다.
- 파일 앞뒤의 빈 줄은 무시됩니다. 섹션 사이 간격은 코드가 붙입니다.
- 새 프롬프트를 추가하면 `load()/render()/sections()/agent_spec()` 로 읽으세요. 사용되지 않는 파일이나 없는 파일을 가리키는
  참조는 `tests/unit/test_prompts.py` 가 잡아냅니다.

## 파일 목록

### 메인 에이전트 시스템 프롬프트 (요청마다 조립: `agent/orchestrator.py`)
| 파일 | 내용 | 사용처 |
|---|---|---|
| `system.md` | 기본 시스템 프롬프트 (응답 범위 원칙, 도구 사용 규칙, 위젯·스킬 안내) | `prompts/__init__.py` `SYSTEM_PROMPT` |
| `custom_agent.md` | 커스텀 에이전트 지침 머리글 + 사용자 지침 `{{name}}` `{{instructions}}` | `agent/agent_runtime.py` |
| `tool_limit.md` | 도구를 제한한 에이전트의 사용 가능 도구 안내 `{{allowed}}` | `agent/agent_runtime.py` |
| `time_context.md` | 현재 시각 `{{now}}` | `agent/orchestrator.py` |
| `memory_facts.md` `memory_procedures.md` `memory_episodes.md` `memory_short_term.md` | 메모리 구역 머리말 `{{items}}` | `agent/orchestrator.py` |
| `summary_context.md` | 대화 앞부분 요약 구역 `{{summary}}` | `services/conversation_summary.py` |
| `mcp_catalog.md` | MCP 도구 목록 머리말 `{{tools}}` | `tools/mcp_tools.py` |
| `headless.md` | 예약(무인) 실행 지침 | `agent/orchestrator.py` |
| `scope_reminder.md` | 마지막 사용자 메시지 끝에 붙는 응답 범위 안내 (LLM 입력에만) | `agent/scope.py` |

### 팀·서브에이전트 (`agent/agno_engine.py`, `tools/`)
| 파일 | 내용 |
|---|---|
| `team_default.md` | 기본 팀 리더 지침 (문단 목록) |
| `team_custom.md`, `team_custom_delegate.md` | 직접 구성·단독 모드 리더 지침, 서브에이전트가 있을 때만 붙는 위임 지침 |
| `subagent_research.md` `subagent_coder.md` `subagent_explorer.md` | 기본 서브에이전트의 역할(첫 문단)과 지침 |
| `browser_agent.md` | 브라우저 에이전트 지침 (문단 목록, `tools/browser_tools.py`) |
| `sub_agent_task.md` | `call_sub_agent` 가 서브에이전트에 넘기는 작업과 `[Context]` 형식 |

### 별도 LLM 호출
| 파일 | 용도 | 사용처 |
|---|---|---|
| `intent_gate.md` | 요청/서술 분류와 서술 반응문 생성 | `agent/intent.py` |
| `memory_extraction.md` | 대화에서 메모리 추출 (사실/작업 방식/사례/단기) | `services/memory_extractor.py` |
| `summary_request.md` | 대화 롤링 요약 | `services/conversation_summary.py` |
| `image_analysis.md` | `read_image` 의 기본 분석 질문 | `tools/workspace_tools.py` |
| `scheduled_run.md` | 예약 실행 때 사용자 메시지 앞에 붙는 머리말 | `services/task_runner.py` |

### 도구가 모델에게 돌려주는 안내 문구
| 파일 | 사용처 |
|---|---|
| `tool_error_quote_missing.md` `tool_error_quote_mismatch.md` | `tools/schedule_tool.py` (이전 요청 재실행 방지) |
| `tool_result_headless_ask.md` | `tools/interaction_tools.py` (예약 실행 중 질문 불가) |

## 이 폴더에 없는 것
도구의 `description`과 인자 설명(`tools/*.py`의 Field description)은 도구 스키마의 일부라서 각 도구 코드에 있습니다.
`create_widget`의 위젯 형식 설명도 같습니다. 화면용 문구(도구 카탈로그 한국어 설명, 에이전트 템플릿 지침)는 LLM 프롬프트가 아닙니다.
