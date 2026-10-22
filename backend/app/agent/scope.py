"""응답 범위 제한: 에이전트가 '마지막 사용자 메시지'가 요청한 것에만 답하도록 한다.

대화 기록을 실제 턴으로 다시 보여 주면 모델이 이전 요청(예: 주가 조회)을 새 메시지에도 이어서 수행하는 일이 있다.
가장 최근 위치(마지막 사용자 메시지 끝)에 짧은 안내를 붙여 이를 막는다. 안내 문구는 prompts/scope_reminder.md 이고,
LLM 입력에만 들어가며 DB·화면에는 남지 않는다.
"""
from app.agent.prompts import load


def with_scope_reminder(user_input: str, has_history: bool) -> str:
    """이전 대화가 있을 때만 마지막 사용자 메시지 뒤에 범위 안내를 붙인다."""
    return user_input + "\n\n" + load("scope_reminder") if has_history else user_input
