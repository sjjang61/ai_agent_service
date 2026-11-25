# AI Agent Browser (Chrome 확장)

일반 Chrome(전용 프로필 권장)의 탭 하나를 AI Agent 플랫폼이 조작하게 한다. 앱 브라우저가 봇 차단되는 사이트(예: 쿠팡)용.
CDP(debugger)·쿠키 권한은 쓰지 않는다. 연결돼 있는 동안 이 사용자의 브라우저 작업은 모두 이 확장으로 간다 (`EXT_BROWSER_ENABLED`).

## 설치
1. 전용 Chrome 프로필을 만든다 (프로필 추가).
2. `chrome://extensions` → 개발자 모드 → "압축해제된 확장 프로그램을 로드합니다" → 이 폴더.
3. 플랫폼 설정 > 브라우저 로그인 > "일반 Chrome 으로 조작"에서 연결 토큰을 만든다.
4. 확장 아이콘 팝업에 서버 주소(`ws://127.0.0.1:8500`)와 토큰을 넣고 "저장하고 연결". 상태가 "연결됨"이면 된다.

## 구성
- `background.js` — 서버(`/ws/ext`)에 접속해 명령(goto/snapshot/click/type/press/select/scroll/back/reload/frame/screenshot)을 처리.
- `snap.js`, `blocked.js`, `dialogs.js` — 서버 규칙(`SNAP_JS`, `BLOCKED_JS`, 대화상자 허용 규칙)에서 **생성**한 파일. 직접 고치지 말고 `cd backend && ../.venv/bin/python scripts/export_snap_js.py`.
- 팝업의 "조작 중지"를 누르면 진행 중이던 작업은 더 조작하지 않는다. 명령을 처리하는 동안 아이콘에 빨간 점이 뜬다.

## 시험
`cd backend && ../.venv/bin/python -u scripts/ext_e2e.py` — Chromium 에 확장을 올려 로컬 페이지에서 8가지 동작을 확인한다.
