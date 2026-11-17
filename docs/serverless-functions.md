# Functions (Lambda 형 실행) 상세 스펙 · 진행 계획 · 리뷰

> 상태: **설계 초안 (미구현)**. 6장의 결정 필요 항목에 답하면 확정한다.
> 관련 문서: [sandbox-isolation.md](sandbox-isolation.md), [deploy-architecture.md](deploy-architecture.md)

## 1. 목적과 범위

개발한 코드를 **zip 으로 패키징해 드라이브에 등록**해 두고, **실행 시점에 새 격리 환경을 만들어 코드를 올려 실행한 뒤 환경을 폐기**한다.
등록·실행·이력 관리는 **Workflow 메뉴**에서 한다. AWS Lambda 의 "요청마다 새 환경에서 실행, 끝나면 종료" 모델을 따른다.

| 구분 | 내용 |
|---|---|
| 하는 것 | zip 등록·버전 관리, 실행마다 새 컨테이너, 입력(JSON)→출력(JSON)·로그 수집, 타임아웃·자원 제한, 실행 이력·취소, 예약/수동/API 실행 |
| 안 하는 것 (이번 범위 밖) | 함수끼리 이어 붙이는 DAG 편집기, 상시 실행 서버(→ 웹앱 배포가 담당), GPU, 다중 리전, 과금 |
| 웹앱 배포와의 차이 | 웹앱(`published_apps`)은 **오래 떠 있는 HTTP 서버**(요청 시 깨움, 유휴 종료). Function 은 **한 번 실행하고 끝나는 작업**이다. 두 기능은 컨테이너 생성 코드만 공유한다 |

용어: **Function**(이름 있는 실행 단위) · **Version**(불변 zip 스냅샷) · **Run**(1회 실행 기록) · **Trigger**(실행 방법: 수동/API/예약/웹훅/에이전트)

## 2. 현재 코드에서 재사용할 수 있는 것

| 필요 | 재사용 대상 | 비고 |
|---|---|---|
| 컨테이너 생성·격리 옵션 | `SandboxManager.create_app_container` ([manager.py](../backend/app/sandbox/manager.py)) | `cap_drop=ALL`, `no-new-privileges`, mem/cpu 제한, 전용 네트워크가 이미 있다. **`pids_limit`·읽기 전용 루트는 없어서 추가 필요** |
| 파일 주입·실행·수집 | `put_archive_file`, `exec_with_rpc`, `export_path`, `read_file` | 같은 Docker SDK 경로 |
| 아카이브 검증 | `normalize_archive` ([app_artifact.py](../backend/app/services/app_artifact.py)) | **tar 용**이다. zip 은 심볼릭 링크·경로·압축 폭탄 검증을 새로 써야 한다 |
| 저장소 | MinIO 비공개 버킷(`MINIO_BUCKET`, 백업용), `object_storage.py` | 현재 `object_storage.py` 는 **공개 버킷 업로드** 중심. 비공개 키 업/다운로드 함수를 추가해야 한다 |
| 예약 | `core/scheduler.py` 의 조건부 UPDATE 선점 패턴, `schedule_calc.compute_next_run` | `ScheduledTask` 는 **에이전트 프롬프트 실행용**이라 Function 용 트리거는 별도 테이블로 두고 계산·선점 로직만 공유 |
| 유휴/고아 정리 | `sandbox/reaper.py`, `app_host.run_app_reaper` | 같은 방식의 Function 컨테이너 reaper |
| 암호화 | `crypto` (Fernet, 커넥터 토큰에 사용) | 환경변수 시크릿 저장 |
| 메뉴 | `IconBar.tsx`, `App.tsx` 라우트 | Workflow 아이콘 추가 |

**없는 것**: "드라이브"라는 자체 기능은 없다(Google Drive 커넥터는 읽기 전용). → 6장 Q1.

## 3. 상세 스펙

### 3.1 패키지 규약 (zip)

```
my-func.zip
├── function.json        # 필수. 메타데이터 (아래)
├── main.py              # handler 가 있는 파일 (python) 또는 index.ts/js (bun)
└── ...                  # 의존성은 zip 안에 포함(vendored). 예: pip install -t ./ 
```

`function.json`:
```json
{
  "name": "daily-report",
  "runtime": "python3.12",          // python3.12 | bun
  "handler": "main.handler",        // 파일.함수
  "timeout_seconds": 30,
  "memory_mb": 256,
  "allow_network": false,
  "env": { "LOG_LEVEL": "info" }    // 비밀이 아닌 값만. 비밀은 UI 의 시크릿으로 등록
}
```

핸들러 규약: `handler(event: dict, context) -> dict` (JSON 직렬화 가능). `context` 에는 `run_id`, `function`, `version`, `remaining_ms()`, `log(msg)`.
플랫폼이 **부트스트랩 shim** 을 컨테이너에 넣어 import → 호출 → 결과를 지정 경로(`/run/out/result.json`)에 쓴다. 사용자 코드는 stdin/stdout 규약을 몰라도 된다.

| 항목 | 한도(기본, `.env` 로 변경) |
|---|---|
| zip 크기(압축) / 풀었을 때 | 50MB / 250MB |
| 파일 수 | 10,000 |
| 입력 event / 결과 | 256KB / 1MB (초과 시 실패) |
| 로그 | 실행당 1MB (초과분 버림, 잘림 표시) |
| 타임아웃 | 기본 30초, 최대 900초 |
| 메모리 / CPU | 기본 256MB·0.5 core, 최대 1024MB·1 core |

### 3.2 등록·버전

1. 업로드(UI) 또는 sandbox 폴더 → "함수로 등록"(에이전트 도구, 3.7)
2. **검증**: zip 구조, 경로 탈출(`..`, 절대 경로), 심볼릭·하드 링크, 장치 파일, 압축 폭탄(비율·총량), `function.json` 스키마, 핸들러 파일 존재
3. **불변 저장**: `functions/{user_id}/{function_id}/{version}.zip` + sha256. 같은 내용은 새 버전을 만들지 않는다
4. Version 번호는 1부터 증가. `latest` 별칭과 사용자 지정 별칭(`prod`)을 지원하고, **트리거는 별칭 또는 고정 버전**을 가리킨다 (예약이 의도치 않은 새 코드로 바뀌지 않게)
5. 삭제는 소프트 삭제 후 보존 기간 뒤 영구 삭제. 실행 중인 Run 이 있으면 거부

### 3.3 실행 흐름 (요청마다 새 환경)

```
invoke ─▶ [검증: 소유자·한도·동시성] ─▶ Run(queued)
          ─▶ 디스패처가 선점(조건부 UPDATE) ─▶ starting
          ─▶ 컨테이너 생성(라벨 agent-fn-run) ─▶ zip 다운로드·sha256 확인·풀기 ─▶ running
          ─▶ shim 실행 (타임아웃 감시) ─▶ result.json·로그 수집
          ─▶ 컨테이너 강제 제거(항상, finally) ─▶ succeeded | failed | timeout | cancelled
```

- **상태**: `queued → starting → running → succeeded | failed | timeout | cancelled | rejected` (한도 초과 등 시작 못 한 것은 `rejected`)
- **종료 사유**: 정상(exit 0 + result), 핸들러 예외(traceback 을 로그에 남김, `failed`), 타임아웃(컨테이너 kill, `timeout`), OOM(137 + `OOMKilled`, `failed: out_of_memory`), 취소(`cancelled`)
- **동기 실행**: `POST /invoke?wait=true` 는 최대 `FUNCTION_SYNC_WAIT_SECONDS`(기본 30) 대기, 넘으면 202 + `run_id` 로 전환
- **재시도**: 기본 0회(at-most-once). 비동기 트리거는 선택적으로 최대 2회, 간격 고정 — **멱등하지 않은 함수는 재시도를 켜지 않도록 UI 에 경고**
- **콜드 스타트**: 매번 새 컨테이너라 약 1~2초 추가(로컬 이미지 기준, **PoC 에서 실측 필요**). warm pool 은 후속(Phase 4)

### 3.4 격리 (컨테이너 옵션)

| 항목 | 값 |
|---|---|
| 이미지 | 전용 런타임 이미지(`fn-runtime-python`, `fn-runtime-bun`) — 개발용 sandbox 이미지의 도구(git, 브라우저 등)를 빼서 공격면·용량 축소 |
| 사용자 | uid 1000, `no-new-privileges`, `cap_drop=ALL` |
| 파일시스템 | **루트 읽기 전용** + `/tmp`(tmpfs 64MB) + `/run/out`(결과) + `/var/task`(zip 푼 곳, 읽기 전용) |
| 자원 | `mem_limit`, `memswap_limit=mem_limit`(스왑 금지), `cpu_quota`, **`pids_limit=128`**(fork bomb), `ulimit nofile` |
| 네트워크 | **기본 `none`**. `allow_network=true` 면 전용 egress 네트워크(컨테이너 간 icc 차단). 호스트·내부 대역 접근 차단은 [sandbox-isolation.md](sandbox-isolation.md) 의 "남은 위험"과 같은 조치가 선행되어야 한다 |
| 시크릿 | 실행 시점에 환경변수로만 주입(이미지·zip 에 넣지 않음). 로그에서 값은 `***` 로 치환 |
| 마운트 | **호스트 볼륨 없음**, docker.sock 없음. Run 간 공유되는 디스크 없음 |
| 시간 | 플랫폼이 벽시계 기준으로 강제 종료 (코드가 자체 타임아웃을 안 걸어도 끝난다) |

### 3.5 데이터 모델

```
functions            id, user_id, name(UNIQUE per user), description, runtime, default_alias,
                     deleted_at, created_at, updated_at
function_versions    id, function_id, version, sha256, size_bytes, storage_key,
                     config(JSON: handler, timeout, memory, cpu, allow_network, env), created_at
function_aliases     function_id, alias, version_id
function_secrets     function_id, key, value_enc(Fernet)            # 값은 조회 API 에서 반환하지 않는다
function_runs        id, function_id, version_id, user_id, trigger(manual|api|schedule|webhook|agent),
                     status, input(JSON), result(JSON), error, exit_code,
                     queued_at, started_at, finished_at, duration_ms, cold_start_ms, max_memory_mb,
                     log_tail(TEXT 64KB), log_key(MinIO, 전체), attempt, parent_run_id, cancel_requested
function_triggers    id, function_id, alias_or_version, kind(schedule|webhook),
                     schedule_*(기존 schedule_calc 필드), webhook_token_hash, enabled, next_run_at
```

인덱스: `function_runs(user_id, queued_at DESC)`, `(function_id, queued_at DESC)`, `(status)`(디스패처/reaper).
주의: `messages` 에서 겪은 것처럼 **큰 JSON 열(`input`/`result`)을 목록 조회에서 읽지 않는다**(MySQL sort memory 1038).

### 3.6 API

| Method | Path | 설명 |
|---|---|---|
| GET/POST | `/api/functions` | 목록 / 생성(+zip 업로드, multipart) |
| GET/PUT/DELETE | `/api/functions/{id}` | 상세·설정·삭제 |
| POST | `/api/functions/{id}/versions` | 새 버전 업로드 |
| GET | `/api/functions/{id}/versions` | 버전 목록 |
| PUT | `/api/functions/{id}/aliases/{alias}` | 별칭 지정 |
| PUT/DELETE | `/api/functions/{id}/secrets/{key}` | 시크릿 등록·삭제(값 조회 불가) |
| POST | `/api/functions/{id}/invoke` | 실행 (`{event, alias|version, wait}`) → `{run_id, status, result?}` |
| GET | `/api/runs?function_id=&status=` | 실행 이력(목록은 가벼운 열만) |
| GET | `/api/runs/{id}` | 실행 상세(입력·결과·오류) |
| GET | `/api/runs/{id}/logs?after=` | 로그(증분 폴링, 후속에 SSE) |
| POST | `/api/runs/{id}/cancel` | 취소 |
| POST/GET/PUT/DELETE | `/api/functions/{id}/triggers` | 예약·웹훅 트리거 |
| POST | `/hooks/fn/{token}` | 웹훅 수신(로그인 없음, 토큰 해시 검증, 레이트 리밋) |

모든 `/api/*` 는 소유자 검증. 웹훅 토큰은 해시만 저장하고 재발급으로 폐기한다.

### 3.7 에이전트 연동

- `register_function(path)` 도구: sandbox 의 폴더를 zip 으로 만들어 등록(웹앱의 `deploy_web_app` 와 같은 흐름). 프롬프트에 규약(3.1)을 짧게 안내
- `invoke_function(name, event)` 도구: 에이전트가 등록된 함수를 실행하고 결과를 받는다. **쓰기/외부 영향이 있는 함수는 승인 대상**으로 둘 수 있게 함수 설정에 `requires_approval` 을 둔다

### 3.8 Workflow 메뉴 (UI)

IconBar 에 "Workflow" 추가 → `/workflow`:

| 탭 | 내용 |
|---|---|
| 함수 | 목록(이름·런타임·최근 실행 상태·버전), 새 함수(zip 업로드), 상세: 버전·별칭·설정·시크릿·**테스트 실행**(JSON 입력 → 결과·로그) |
| 실행 이력 | 필터(함수/상태/기간), 상태·소요시간·트리거, 상세(입력/결과/로그/오류), **취소** 버튼, 같은 입력으로 재실행 |
| 트리거 | 예약(기존 예약 UI 컴포넌트 재사용), 웹훅 URL 발급·재발급 |

실행 중 Run 은 상세에서 2초 폴링(후속 SSE). 실패한 최근 실행이 있는 함수는 목록에 배지.

### 3.9 설정(`.env`)

```
FUNCTION_ENABLED=false                  # 기본 꺼짐. 켜기 전에 8장 선행 조건 확인
FUNCTION_RUNTIME_IMAGE_PYTHON=ai-agent-fn-python:latest
FUNCTION_RUNTIME_IMAGE_BUN=ai-agent-fn-bun:latest
FUNCTION_MAX_CONCURRENT_PER_USER=3
FUNCTION_MAX_CONCURRENT_GLOBAL=20
FUNCTION_QUEUE_MAX_PER_USER=20
FUNCTION_RUNS_PER_DAY_PER_USER=500
FUNCTION_PACKAGE_MAX_MB=50
FUNCTION_TIMEOUT_DEFAULT=30
FUNCTION_TIMEOUT_MAX=900
FUNCTION_SYNC_WAIT_SECONDS=30
FUNCTION_RUN_RETENTION_DAYS=30          # Run 이력·로그 보존
FUNCTION_ALLOW_NETWORK=false            # 서버 전체에서 egress 허용 여부 (함수별 allow_network 의 상한)
```

## 4. 진행 계획

| 단계 | 기간(1인) | 내용 | 완료 기준 |
|---|---|---|---|
| **P0 확정·PoC** | 2~3일 | 6장 결정, 격리 PoC(읽기 전용 루트·tmpfs·pids·network none 에서 python/bun 실행), **콜드 스타트 실측**, zip 검증기 | 악성 zip 샘플(경로 탈출, 폭탄, 심볼릭) 전부 거부, fork bomb·메모리 폭주가 호스트에 영향 없음, 콜드 스타트 수치 기록 |
| **P1 코어(백엔드)** | 1.5주 | 모델·마이그레이션, 패키지 저장소(MinIO 비공개), 검증·버전, 러너(shim)+`RuntimeBackend` 인터페이스(Docker 구현), 디스패처(선점)·동시성·쿼터, Run 상태머신·취소·타임아웃, reaper(시작 시 고아 컨테이너 정리), API | 수동/API 로 등록·실행·결과·로그·취소, 서버 재시작 후 고아 컨테이너 0, 단위·통합 테스트 |
| **P2 Workflow UI** | 1주 | 메뉴·라우트, 함수 목록/상세, 업로드, 테스트 실행, 실행 이력·상세·취소 | 브라우저에서 업로드→실행→로그 확인 |
| **P3 트리거·에이전트** | 1주 | 예약, 웹훅, `register_function`/`invoke_function` 도구, 재시도 정책 | 예약이 한 번만 실행(다중 프로세스), 에이전트가 만든 코드를 함수로 등록·실행 |
| **P4 하드닝·운영** | 1주+ | egress 허용 목록, 의존성 빌드 단계, warm pool, 메트릭(Opik/Prometheus), 별도 러너 호스트/K8s Job 백엔드, 감사 로그 | 부하 테스트(동시 N)와 장애 주입 결과 문서화 |

총 **약 4.5~5.5주**. P1 의 `RuntimeBackend` 추상화가 P4 의 K8s/원격 호스트 전환 비용을 결정하므로 P1 에서 인터페이스를 지킨다.

### 테스트 계획

- 단위: zip 검증(악성 샘플 목록), 상태 전이, 쿼터·동시성, 시크릿 마스킹, 타임아웃 계산
- 통합(Docker 필요): 정상/예외/타임아웃/OOM/취소/출력 초과, 네트워크 차단(외부·호스트·내부 서비스로의 연결 실패 확인), 읽기 전용 루트 쓰기 실패, 고아 정리
- 동시성: 한 함수 N 동시 실행, 사용자 한도 초과 시 `rejected`/대기, 서버 2프로세스에서 예약 중복 실행 없음
- UI: 업로드 오류 메시지, 로그 폴링, 취소 반영

## 5. 리뷰 (발견한 문제와 권고)

### 5.1 심각도 높음

1. **"사용자가 올린 임의 코드를 자동·예약으로 실행"은 개발 sandbox 보다 위험하다.** sandbox 는 사용자가 직접 대화 중에 쓰지만 Function 은 무인으로 반복 실행된다 → 채굴·스팸·스캔 남용 경로가 된다.
   → 기본 `FUNCTION_ENABLED=false`, 네트워크 기본 차단, 쿼터(일 실행 수·총 CPU 시간), 관리자 즉시 중지 스위치(사용자/함수 단위), 실행 감사 로그를 P1 범위에 **필수**로 넣는다. 이 항목은 P4 로 미루지 않는다.
2. **호스트 서비스 접근 문제가 그대로 남는다.** [sandbox-isolation.md](sandbox-isolation.md) 가 이미 지적한 `host.docker.internal`·내부 대역 접근은 `allow_network=true` 에서 재현된다. → egress 를 켜는 기능은 **호스트 방화벽(DOCKER-USER)/NetworkPolicy 적용 확인 전에는 배포 금지**. `none` 모드만으로 MVP 를 먼저 낸다.
3. **백엔드 프로세스가 docker.sock 을 쥐고 직접 컨테이너를 돌리는 구조의 한계.** 동시 실행이 늘면 백엔드(API)와 실행이 자원을 다툰다. → 디스패처를 DB 선점 방식으로 만들어 **API 프로세스와 분리 가능**하게 하고(P1), 운영에서는 별도 러너 호스트를 권장한다(P4).
4. **"드라이브"가 정의되어 있지 않다.** 6장 Q1 에 따라 저장 계층 구현량이 크게 달라진다(내부 MinIO면 쉬움, 사용자 Google Drive 면 OAuth 범위 확대·권한·변경 감지가 필요).

### 5.2 중간

5. **의존성 처리**: "zip 에 vendoring" 을 요구하면 사용자가 sandbox 에서 `pip install -t` 로 직접 만들어야 한다(에이전트는 가능). 플랫폼 빌드 단계는 네트워크 egress 가 필요해 P4. MVP 는 **vendoring 규약 + 에이전트가 패키징해 주는 도구**로 간다.
6. **컨테이너 이미지 분리 필요**: 현재 sandbox 이미지(브라우저 등 포함)를 그대로 쓰면 이미지가 크고 콜드 스타트가 느리며 공격면이 넓다 → 런타임 전용 슬림 이미지.
7. **재시도·멱등성**: 기본 재시도 0. 외부 부작용이 있는 함수에 자동 재시도를 켜면 중복 실행이 생긴다 — UI 경고와 `idempotency_key`(API) 를 P3 에서 지원.
8. **로그 비밀 누출**: 시크릿이 출력에 찍힐 수 있다 → 값 마스킹(완전하지 않음을 문서화), 로그 접근은 소유자만.
9. **다중 서버 일관성**: Run 선점은 스케줄러와 같은 조건부 UPDATE. 서버 크래시 시 `starting/running` 으로 남은 Run 은 reaper 가 `failed(infrastructure)` 로 정리(라벨로 컨테이너 대조).
10. **큰 입출력**: DB JSON 에 1MB 까지 넣으면 이력이 비대해진다 → 목록은 요약만, 보존기간 후 정리, 큰 결과는 MinIO.

### 5.3 낮음 / 확인 필요

11. 이름: "Workflow" 는 보통 **여러 단계의 연결**을 뜻한다. 현재 스펙은 함수 단건 실행이다. 메뉴 이름은 Workflow 로 두되 DAG(함수 체이닝)는 후속임을 화면에 드러내거나, 메뉴명을 "Functions" 로 하는 것도 가능(Q2).
12. 런타임: 지금 이미지에 확인된 것은 Python 3.12 와 Bun. Node/그 외는 이미지 추가 비용이 든다(MVP: python, bun).
13. 시간대·예약 정밀도는 기존 스케줄러(분 단위 폴링)를 따른다. 초 단위 정밀도는 보장하지 않는다.
14. Windows/macOS 개발 환경의 Docker Desktop 에서는 `pids_limit`·메모리 제한 동작이 리눅스와 다를 수 있어 **통합 테스트는 리눅스 CI 에서도 확인**한다.

### 5.4 이 스펙에서 검증되지 않은 가정

- 콜드 스타트 1~2초(실측 전)
- sandbox 이미지의 Python/Bun 외 런타임 유무
- MinIO 비공개 버킷에 임의 키로 업/다운로드 시 현재 권한 설정으로 충분한지
- 현재 운영 환경이 단일 호스트(docker.sock 접근 가능)라는 전제

## 6. 결정이 필요한 항목

| # | 질문 | 권고 |
|---|---|---|
| Q1 | **"드라이브"는 무엇인가?** ✅ **결정됨: 서비스 자체 개인 파일 공간(MinIO 기반 신규) — [drive.md](drive.md).** (아래는 결정 전 검토 내용) ① 서비스 자체 파일 저장소(MinIO, 신규) ② 사용자의 Google Drive ③ 둘 다 | **① 로 시작**하고 저장 계층을 인터페이스(`PackageStore`)로 분리해 ② 를 후속에 붙인다. ② 를 먼저 하려면 커넥터 Drive 범위를 읽기/쓰기로 올려야 하고 일정이 +1~2주 |
| Q2 | Workflow 메뉴의 범위: 함수 단건 실행 관리만? 함수 연결(순차/분기)까지? | MVP 는 단건. 연결은 P5 로 분리 |
| Q3 | 외부 네트워크 허용 | MVP 는 **차단**. 필요한 사용 사례가 나오면 허용 목록 방식(P4) |
| Q4 | 지원 런타임 | python3.12 + bun(JS/TS) |
| Q5 | 누가 쓰는가: 모든 사용자 / 관리자·허용 사용자만 | 허용 사용자 플래그(관리자 지정)로 시작, 쿼터 필수 |
| Q6 | 실행 서버: 현재 백엔드와 같은 호스트에서 시작해도 되는가 | 가능. 단 5.1-3 에 따라 분리 가능한 구조로 |
| Q7 | 실행 결과 보존 기간 | 30일 |
