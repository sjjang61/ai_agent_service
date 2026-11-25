"""크롬 확장이 쓰는 스크립트(chrome-extension/{snap,blocked,dialogs}.js)를 서버의 규칙과 같은 내용으로 만든다.
실행: cd backend && ../.venv/bin/python scripts/export_snap_js.py   (SNAP_JS·BLOCKED_JS·대화상자 규칙을 고치면 다시 실행; 테스트가 어긋남을 잡는다)"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.services.browser_policy import _DIALOG_DENY, _DIALOG_OK  # noqa: E402
from app.services.browser_snapshot import BLOCKED_JS, SNAP_JS  # noqa: E402

DIALOGS_JS = r"""(() => {
  if (window.__agentDialogsInstalled) return; window.__agentDialogsInstalled = true;
  const OK = new RegExp(%OK%), DENY = new RegExp(%DENY%);
  const rec = (s) => { try { const a = JSON.parse(sessionStorage.getItem('__agentDialogs') || '[]'); a.push(String(s).slice(0, 240)); sessionStorage.setItem('__agentDialogs', JSON.stringify(a.slice(-5))); } catch (_) {} };
  window.alert = (m) => { rec('확인 처리한 alert 대화상자: ' + m); };
  window.confirm = (m) => { m = String(m == null ? '' : m); const ok = OK.test(m) && !DENY.test(m); rec((ok ? '확인' : '취소') + ' 처리한 confirm 대화상자: ' + m); return ok; };
  window.prompt = (m) => { rec('취소 처리한 prompt 대화상자: ' + m); return null; };
})();
"""


def render() -> dict:
    return {
        "snap.js": SNAP_JS,
        "blocked.js": "globalThis.__agentBlocked = " + BLOCKED_JS + ";\n",
        "dialogs.js": DIALOGS_JS.replace("%OK%", json.dumps(_DIALOG_OK.pattern)).replace("%DENY%", json.dumps(_DIALOG_DENY.pattern)),
    }


if __name__ == "__main__":
    d = pathlib.Path(__file__).resolve().parents[2] / "chrome-extension"
    for name, text in render().items():
        (d / name).write_text(text, encoding="utf-8")
        print("wrote", d / name)
