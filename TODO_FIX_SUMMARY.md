# Todo 재실행 문제 수정 완료

## 문제 상황
사용자가 "피보나치 수열 코드 생성" 요청 후 "주식 조회" 요청을 했을 때, 첫번째 요청(피보나치)이 다시 실행되는 문제가 발생했습니다.

## 근본 원인 분석

### 1. 대화 컨텍스트 로딩
- `ConversationMemory.from_db_messages()`는 최근 20개의 메시지를 로드
- 이전 요청의 미완료 todo가 컨텍스트에 포함됨

### 2. Agent의 해석
- Agent는 대화 기록을 보고 미완료 todo를 발견
- 시스템 프롬프트에 "todo를 갱신하세요"라는 지침이 있음
- Agent가 이를 "완료해야 할 작업"으로 해석하여 재실행

### 3. Todo 저장 구조
- Todo는 백엔드 메모리(_todo_store)에 conversation_id별로 저장
- 각 메시지의 agent_steps에도 todo 상태가 저장됨
- UI는 agent_steps의 todo를 표시

## 구현한 해결 방안

### 방안 1: Auto-complete 메커니즘 (✅ 구현 완료)

**파일**: `backend/app/tools/interaction_tools.py`
```python
def complete_all_todos(conversation_id: str) -> None:
    """
    새 사용자 요청 시작 시 이전 작업의 미완료 todo를 모두 completed로 변경한다.
    """
```

**위치**: `backend/app/agent/orchestrator.py` - `run()` 메서드 시작 부분
```python
async def run(self, user_input: str, conversation_id: str, db: AsyncSession):
    # 새 요청 시작 시 이전 작업의 미완료 todo를 모두 completed로 변경
    complete_all_todos(conversation_id)
```

**동작 방식**:
1. 새 요청이 들어올 때마다 자동 실행
2. 해당 대화의 모든 미완료 todo를 "completed" 상태로 변경
3. Agent가 todo tool을 호출하면 이미 완료된 상태로 표시됨
4. 이전 작업을 다시 수행하지 않음

### 방안 2: 시스템 프롬프트 개선 (✅ 구현 완료)

**파일**: `backend/app/agent/prompts/system_prompt.md`
```markdown
- 3단계 이상의 작업은 시작할 때 `todo` 로 계획을 세우고, 진행하면서 상태를 갱신하세요.
  **중요**: 과거 대화에서 미완료된 todo가 보이더라도 무시하세요.
  오직 현재 사용자 요청에 대한 작업만 수행하세요. 새 요청마다 새로운 계획을 세우세요.
```

**효과**:
- Agent에게 명시적으로 과거 todo를 무시하도록 지시
- 현재 요청에만 집중하도록 유도
- 새 요청마다 새로운 todo 계획을 세우도록 안내

## 디버깅 로깅 추가

### orchestrator.py
```python
print(f"\n{'='*80}")
print(f"[ORCHESTRATOR RUN] 새 요청 시작")
print(f"  conversation_id: {conversation_id}")
print(f"  user_input: {user_input[:200]}")
print(f"{'='*80}\n")
```

### interaction_tools.py - complete_all_todos()
```python
print(f"\n[COMPLETE_ALL_TODOS] Called for conversation: {conversation_id[:16]}...")
print(f"  Current todos in store: {len(current)}")
print(f"  Incomplete todos: {incomplete_count}")
if incomplete_count > 0:
    print(f"  -> Marking {incomplete_count} todos as completed:")
    for todo in current:
        if todo["status"] != "completed":
            print(f"     - [{todo['id']}] {todo['content'][:60]} ... ({todo['status']} -> completed)")
```

## 테스트 방법

### 1. 서버 재시작 확인
서버가 자동으로 재시작되었는지 확인:
```bash
tail -f /tmp/backend.log
# "Started server process [XXXXX]" 메시지 확인
```

### 2. 테스트 시나리오
1. **첫번째 요청**: "피보나치 수열을 계산하는 Python 코드를 작성해줘"
   - Agent가 todo를 생성하고 작업을 수행
   - 완료 후 todo가 "completed" 상태가 됨

2. **두번째 요청**: "SK하이닉스 주식 정보를 조회해줘"
   - 서버 로그에 디버그 출력 확인:
     ```
     [ORCHESTRATOR RUN] 새 요청 시작
     [COMPLETE_ALL_TODOS] Called for conversation: 6b8c8e28-dfad-...
       -> Marking N todos as completed:
          - [1] 피보나치 수열 코드 작성 ... (in_progress -> completed)
     ```
   - Agent가 **피보나치 작업을 재실행하지 않음**
   - 주식 조회만 수행

### 3. 예상 결과

**Before (문제 상황)**:
```
User: "SK하이닉스 주식 정보 조회해줘"
Agent:
  1. 피보나치 코드를 다시 작성 시작 (❌ 잘못된 동작)
  2. 주식 정보 조회
```

**After (수정 후)**:
```
User: "SK하이닉스 주식 정보 조회해줘"
Agent:
  1. 주식 정보만 조회 (✅ 올바른 동작)
```

## 로그 확인 방법

테스트 후 로그를 확인하여 fix가 작동하는지 검증:

```bash
# 실시간 로그 모니터링
tail -f /tmp/backend.log

# 또는 최근 100줄 확인
tail -100 /tmp/backend.log | grep -A 10 "ORCHESTRATOR\|COMPLETE_ALL_TODOS"
```

로그에서 확인할 내용:
- `[ORCHESTRATOR RUN]` - 새 요청이 시작됨
- `[COMPLETE_ALL_TODOS]` - Todo 자동 완료 함수가 호출됨
- `Marking N todos as completed` - 미완료 todo가 있었고 완료 처리됨
- `No todos found` 또는 `All todos already completed` - 완료할 todo가 없음

## UI 동작 설명

### 과거 메시지의 Todo 표시
- **현상**: 새로고침 후에도 과거 메시지의 미완료 todo가 보임
- **이유**: UI는 각 메시지의 `agent_steps`에서 todo를 읽어 표시
- **정상**: 과거 메시지는 역사적 기록이므로 당시 상태를 그대로 표시하는 것이 정상
- **중요**: 표시되는 것과 재실행되는 것은 별개의 문제

### 실제 문제
- ❌ **과거 todo가 UI에 표시됨** - 정상 동작 (역사적 기록)
- ✅ **과거 todo가 새 요청에서 재실행됨** - 문제 (이번에 수정함)

## 추가 개선 가능 사항 (선택 사항)

현재 구현으로 충분하지만, 향후 개선 가능한 부분:

1. **UI에서 과거 todo를 숨기기**
   - TodoCard.tsx에서 가장 최근 메시지의 todo만 표시
   - 또는 completed된 todo는 접어서 표시

2. **Todo persistence**
   - 현재는 메모리에만 저장
   - DB에 저장하여 서버 재시작 시에도 유지

3. **Todo 만료 시간**
   - 일정 시간(예: 1시간) 지난 todo는 자동 완료

## 변경된 파일 목록

1. ✅ `backend/app/tools/interaction_tools.py`
   - `complete_all_todos()` 함수 추가
   - 디버그 로깅 추가

2. ✅ `backend/app/agent/orchestrator.py`
   - `run()` 시작 시 `complete_all_todos()` 호출
   - 디버그 로깅 추가

3. ✅ `backend/app/agent/prompts/system_prompt.md`
   - Todo 처리 관련 명확한 지침 추가
   - 과거 todo 무시 명시

## 결론

**3가지 레이어**에서 문제를 해결:

1. **백엔드 로직**: 새 요청마다 자동으로 이전 todo 완료 처리
2. **시스템 프롬프트**: Agent에게 과거 todo 무시 지시
3. **디버그 로깅**: 문제 발생 시 추적 가능

이제 테스트를 진행하여 "피보나치 → 주식 조회" 시나리오에서 피보나치가 재실행되지 않는지 확인해주세요.

---

**마지막 업데이트**: 2026-10-15
**수정한 버전**: backend process [88666]
