"""Python 런타임 부트스트랩: /var/task/function.json 의 handler("파일.함수")를 불러 이벤트를 넘기고 결과를 마커 줄로 내보낸다."""
import asyncio, importlib, inspect, json, os, sys, time, traceback

TOKEN = os.environ.pop("FN_RESULT_TOKEN", "")
START = time.monotonic()
TIMEOUT_MS = int(os.environ.get("FN_TIMEOUT_MS", "30000"))


def emit(obj):
    sys.stdout.flush(); sys.stderr.flush()
    sys.stdout.write(f"\n__FN_RESULT_{TOKEN}__ " + json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


class Context:
    def __init__(self):
        self.run_id = os.environ.get("FN_RUN_ID", "")
        self.function_name = os.environ.get("FN_FUNCTION", "")
        self.version = os.environ.get("FN_VERSION", "")

    def remaining_ms(self):
        return max(0, TIMEOUT_MS - int((time.monotonic() - START) * 1000))

    def log(self, msg):
        print(msg, flush=True)


def main():
    try:
        cfg = json.load(open("/var/task/function.json"))
        mod_name, _, fn_name = cfg["handler"].rpartition(".")
        sys.path.insert(0, "/var/task")
        handler = getattr(importlib.import_module(mod_name), fn_name)
        event = json.load(open("/tmp/event.json"))
        result = handler(event, Context())
        if inspect.isawaitable(result):
            result = asyncio.run(result)
        try:
            json.dumps(result)
        except (TypeError, ValueError) as e:
            raise TypeError(f"핸들러 반환값을 JSON 으로 만들 수 없습니다: {e}")
        emit({"ok": True, "result": result})
    except BaseException as e:  # noqa: BLE001
        traceback.print_exc()
        emit({"ok": False, "error": {"type": type(e).__name__, "message": str(e)[:2000]}})
        sys.exit(1)


main()
