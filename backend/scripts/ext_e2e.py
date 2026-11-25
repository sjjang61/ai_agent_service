"""크롬 확장 실제 시험: Playwright 의 Chromium 에 확장을 올리고, 가짜 서버(/ws/ext)가 명령을 보내 로컬 시험 페이지를 조작한다.
실행: cd backend && ../.venv/bin/python -u scripts/ext_e2e.py   (playwright·websockets 필요, 8/8 이 나와야 한다)"""
import asyncio, json, sys, threading, http.server, socketserver
import websockets
from playwright.async_api import async_playwright
import pathlib, tempfile
EXT = str(pathlib.Path(__file__).resolve().parents[2] / "chrome-extension")
PAGE = b"""<!doctype html><meta charset=utf-8><title>T</title><body>
<form action="/result" method="get"><input name="q" id="q" placeholder="search"><button type="submit" id="go">Search</button></form>
<button id="a" onclick="alert('hello alert');document.title='clicked'">Alert</button>
<button id="c" onclick="document.title=confirm('\\uacb0\\uc81c\\ud558\\uc2dc\\uaca0\\uc2b5\\ub2c8\\uae4c?')?'paid':'cancelled'">Confirm</button>
<select id="s"><option value="1">one</option><option value="2">two</option></select>
</body>"""
RES = b"<!doctype html><title>R</title><body><h1 id=r>RESULT PAGE</h1></body>"
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.end_headers()
        self.wfile.write(RES if self.path.startswith("/result") else PAGE)
    def log_message(self,*a): pass
socketserver.TCPServer.allow_reuse_address = True
srv = socketserver.TCPServer(("127.0.0.1", 18766), H); threading.Thread(target=srv.serve_forever, daemon=True).start()

results = []
def ok(name, cond, extra=""):
    results.append((name, bool(cond))); print(("PASS" if cond else "FAIL"), name, extra if not cond else "")

async def main():
    conn_fut = asyncio.get_event_loop().create_future()
    pending = {}
    conns = []
    async def handler(ws):
        conns.append(1)
        if not conn_fut.done(): conn_fut.set_result(ws)
        async for m in ws:
            d = json.loads(m)
            if "id" in d and d["id"] in pending: pending[d["id"]].set_result(d["result"])
    server = await websockets.serve(handler, "127.0.0.1", 18765)
    seq = [0]
    async def cmd(ws, **c):
        seq[0] += 1; f = asyncio.get_event_loop().create_future(); pending[seq[0]] = f
        await ws.send(json.dumps({"id": seq[0], **c})); return await asyncio.wait_for(f, 40)
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(tempfile.mkdtemp(prefix="ext_e2e_"), channel="chromium", headless=True,
            args=[f"--disable-extensions-except={EXT}", f"--load-extension={EXT}"])
        sw = ctx.service_workers[0] if ctx.service_workers else await ctx.wait_for_event("serviceworker")
        await sw.evaluate("chrome.storage.local.set({server:'ws://127.0.0.1:18765', token:'x'})")
        await sw.evaluate("connect()")
        ws = await asyncio.wait_for(conn_fut, 15)
        r = await cmd(ws, cmd="goto", url="http://127.0.0.1:18766/")
        ok("goto+snapshot", r.get("ok") and any("Search" in (e.get("label") or "") or e.get("tag")=="input" for e in r["elements"]), str(r)[:300])
        els = r["elements"]; print([ (e.get("ref"), e.get("tag"), (e.get('label') or '')[:20]) for e in els][:10])
        def find(pred): return next((e["ref"] for e in els if pred(e)), None)
        inp = find(lambda e: e.get("tag") == "input"); btn_alert = find(lambda e: "Alert" in (e.get("label") or "")); btn_conf = find(lambda e: "Confirm" in (e.get("label") or ""))
        r = await cmd(ws, cmd="click", ref=btn_alert)
        ok("alert auto-answered + noted", r.get("ok") and "대화상자 자동 응답" in r.get("text","") and r.get("title") == "clicked", str(r)[:300])
        r = await cmd(ws, cmd="click", ref=btn_conf)
        ok("confirm(결제) cancelled", r.get("ok") and r.get("title") == "cancelled", str(r)[:300])
        r = await cmd(ws, cmd="type", ref=inp, text="진라면", submit=True)
        ok("type+Enter submits form", r.get("ok") and "/result" in r.get("url","") and "RESULT PAGE" in r.get("text",""), str(r)[:300])
        r = await cmd(ws, cmd="back")
        ok("back", r.get("ok") and r["url"].endswith(":18766/"), str(r)[:200])
        els = r["elements"]; sel = find(lambda e: e.get("tag") == "select")
        r2 = await cmd(ws, cmd="select", ref=sel, text="two"); ok("select", r2.get("ok"), str(r2))
        r = await cmd(ws, cmd="click", ref=99999); ok("click missing ref -> notfound", r.get("notfound"), str(r))
        r = await cmd(ws, cmd="frame"); ok("frame image", r.get("ok") and len(r.get("img","")) > 1000, str(r)[:100])
        n = len(ctx.pages)
        r = await cmd(ws, cmd="close_tab")
        await asyncio.sleep(0.5)
        ok("close_tab closes only the agent tab", r.get("ok") and len(ctx.pages) == n - 1, f"{n} -> {len(ctx.pages)}")
        r = await cmd(ws, cmd="close_tab")
        ok("close_tab with no tab does not open one", r.get("ok") and len(ctx.pages) == n - 1)
        # 연결이 겹쳐 호출돼도(확장 새로고침 직후 등) 서로 끊으며 계속 다시 붙지 않아야 한다
        await sw.evaluate("(async()=>{connect(); connect();})()")
        await asyncio.sleep(3); a = len(conns); await asyncio.sleep(8)
        ok("overlapping connect() settles to one stable connection", len(conns) - a <= 1, f"{a} -> {len(conns)}")
        await ctx.close()
    server.close()
    print("TOTAL", sum(1 for _, c in results if c), "/", len(results))
asyncio.run(main())
