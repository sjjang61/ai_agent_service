# 커스텀 에이전트 (My Agent) 설계

프롬프트·도구·스킬·MCP·서브에이전트를 직접 정한 에이전트를 만들고, 미리보기로 실행해 보고, 저장·발행해서
채팅과 예약에서 쓴다.

## 범위 (결정 사항)
- 배포 범위: **내 채팅에서 선택(A) + 예약 연결(B)**. 다른 사용자 공유·공개 링크·API는 범위 밖.
- 사용 환경: 소수의 신뢰된 사용자. stdio MCP 허용, 샌드박스는 사용자당 1개를 그대로 공유.
- 메모리는 에이전트가 아니라 **사용자 것**이다. 에이전트는 사용자 메모리를 쓰거나(기본) 끌 수 있다.
- 서브에이전트는 선택 사항: 기본 팀 / 직접 구성 / 없음(단독).

## 데이터 모델
| 테이블 | 내용 |
|---|---|
| `agents` | 이름·설명·아이콘, `draft_config`(편집 중 초안), `published_version_id` |
| `agent_versions` | 발행 시점의 불변 설정 스냅샷 (`agent_id`+`version` 유일) |
| `conversations` | `agent_id`, `agent_version_id`(시작 시점의 발행 버전에 고정), `is_test`(빌더 미리보기, 목록 비노출) |
| `scheduled_tasks` | `agent_id` (실행 시점의 최신 발행 버전으로 실행) |

컬럼 보강은 서버 시작 시 `_ensure_agent_columns`가 수행하고, 같은 변경이 alembic `g7a1b2c3d4e5`에 있다.

## AgentConfig (`schemas/agent.py`)
```
prompt   { instructions, starters[] }
model    { llm_provider?, model?, max_iterations? }
tools    { mode: all|selected, allow[] }            # 스킬/MCP 도구는 아래 섹션이 따로 제어
skills   { mode: all|selected|none, names[] }
mcp      { mode: all|selected|none, servers[{name, allowed_tools?}] }
memory   { enabled }
team     { mode: default|custom|none, members[{name, role, instructions, tools[]}] }
```

## 실행 반영 (`agent/agent_runtime.py`, `orchestrator.py`, `agno_engine.py`)
- 시스템 프롬프트 = 기본 프롬프트(응답 범위 원칙 등, 고정) + 에이전트 지침 + (도구 제한 시) 사용 가능 도구 안내.
- 도구: `filter_tools`가 허용 목록으로 거른다. `load_skill`, MCP 3종은 skills/mcp 섹션이 제어한다.
- MCP: `mcp/policy.py`가 서버·도구 단위로 허용 범위를 줄인 클라이언트 복사본을 만든다.
- 팀: `build_team`이 `default`(기존 Research/Coder/Explorer), `custom`(정의한 멤버만, 배정되지 않은 도구는 리더가 직접 사용),
  `none`(멤버 없이 리더 단독)을 구성한다. LangGraph 엔진은 팀 설정을 무시한다(기본 엔진은 Agno).
- 모델 우선순위: 에이전트 설정 > 요청 > 서버 기본값. 제공자가 바뀌면 이전 제공자의 모델명은 이어받지 않는다.
- 메모리를 끄면 장기·단기 메모리 주입과 자동 추출을 모두 건너뛴다. 빌더 미리보기(`is_test`)는 자동 추출도 하지 않는다.

## 저장·발행·롤백
- 초안은 편집 중 자동 저장된다(검증 오류가 있어도 저장 가능).
- 발행: 검증 오류가 없어야 하며 새 버전(`v1, v2…`)이 만들어진다. 새 대화는 발행 버전에 고정되고, 이미 시작한 대화는 기존 버전을 유지한다.
- 롤백(`activate`): 이전 버전을 현재 발행 버전으로 되돌린다. `restore`: 이전 버전의 설정을 초안으로 불러온다.
- 예약은 실행 시점의 현재 발행 버전을 쓴다. 에이전트가 삭제·미발행이면 그 회차는 실패로 기록된다.
- 예약이 참조하는 에이전트는 삭제할 수 없다(409).

## API (`/api/agents`)
`GET ""`, `POST ""`, `GET /catalog`, `POST /validate`, `GET|PUT|DELETE /{id}`, `POST /{id}/duplicate`,
`POST /{id}/publish`, `GET /{id}/versions`, `POST /{id}/versions/{n}/restore`, `POST /{id}/versions/{n}/activate`.
채팅: `POST /api/chat/conversations`에 `agent_id`(+`is_test`), 메시지 전송에 미리보기 전용 `agent_config`(저장 전 편집 내용).
예약: `POST/PUT /api/schedules`에 `agent_id`.

## 검증 규칙 (`validate_config`)
- 오류(발행 차단): 알 수 없는 도구, 지원하지 않는 LLM 종류, 서브에이전트 이름 중복·예약어(`AgentTeam` 등),
  서브에이전트 도구가 에이전트 허용 목록 밖, 역할 설명 없음.
- 주의(발행 가능): 지침 비어 있음, 허용 도구 0개, 설치되지 않은 스킬·MCP 서버 참조, 팀 모드와 멤버 불일치.

## 보안 메모 (신뢰된 소수 사용자 가정)
- 모든 조회·수정은 소유자만 가능하다(타인의 에이전트는 404). 대화 시작·메시지 전송도 소유자 검사를 한다.
- 도구는 위험도(읽기/변경/실행)로 분류해 빌더에 표시한다. stdio MCP는 서버에서 프로세스로 실행되므로 신뢰할 수 있는 서버만 연결한다.
- 공유·공개 배포를 추가할 때 필요한 것: 실행자 권한 MCP 자격증명, 세션별 임시 샌드박스, 에이전트 전용 지식 저장소, 예산·속도 제한.

## 다음 단계
- 에이전트별 토큰 사용량 집계(`token_usages.agent_id`), 테스트 케이스·평가, 프롬프트 개선 보조.
- 팀·조직 공유, 공개 링크, API 키·임베드(위 보안 메모의 선행 조건 필요).
