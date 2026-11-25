// AI Agent 플랫폼(백엔드 /ws/ext)에 접속해 명령을 받아 전용 탭 하나를 조작한다.
// CDP(debugger) 를 쓰지 않는다: 탭 이동은 chrome.tabs, 화면 읽기는 snap.js 주입, 조작은 DOM 이벤트.
let ws = null;
let agentTab = null;
let retry = 0;
let urlHist = []; // 우리가 거쳐 온 주소 (크롬은 사용자 조작 없이 생긴 기록을 '뒤로'에서 건너뛰므로 직접 따라간다)
let sig = null; // 마지막으로 읽은 화면의 요약: 클릭 뒤 화면이 바뀌었는지 보는 용도
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const setStatus = (s) => chrome.storage.local.set({ status: s });

let stopped = false; // 사용자가 '조작 중지'를 눌렀다: 다음 명령이 오면(새 작업) 풀린다
let gen = 0;      // connect() 호출 세대: 겹쳐 호출되면 가장 나중 것만 남긴다
let retryTimer = null;
async function connect() {
  const my = ++gen;
  clearTimeout(retryTimer);
  const { server, token } = await chrome.storage.local.get(['server', 'token']);
  if (my !== gen) return;  // 그 사이 더 새로운 connect() 가 시작됐다
  if (!server || !token) return setStatus('서버 주소·토큰을 입력하세요');
  const old = ws; ws = null;
  if (old) { old.onclose = null; try { old.close(); } catch (_) {} }  // 이전 연결이 닫히며 재연결을 또 부르지 않게 한다
  const sock = new WebSocket(`${server.replace(/\/$/, '')}/ws/ext?token=${encodeURIComponent(token)}`);
  ws = sock;
  sock.onopen = () => { retry = 0; setStatus('연결됨'); sock.send(JSON.stringify({ type: 'hello' })); };
  sock.onmessage = async (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === 'attention') return chrome.action.setBadgeText({ text: msg.message ? '!' : '' });
    if (msg.id === undefined) return;
    if (stopped) { stopped = false; setStatus('연결됨'); }
    let result;
    chrome.action.setBadgeText({ text: '●' }); chrome.action.setBadgeBackgroundColor({ color: '#d33' });
    try { result = await handle(msg); } catch (e) { result = { ok: false, error: String(e && e.message || e) }; }
    chrome.action.setBadgeText({ text: '' });
    try { sock.send(JSON.stringify({ id: msg.id, result })); } catch (_) {}
  };
  sock.onclose = () => {
    if (ws !== sock) return;  // 이미 다른 연결로 바뀌었다
    ws = null; setStatus('연결 끊김 — 재시도 중');
    retryTimer = setTimeout(connect, Math.min(30000, 1000 * 2 ** retry++));
  };
  sock.onerror = () => {};
}
setInterval(() => { if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: 'hello' })); }, 20000); // 서비스 워커가 잠들지 않게
chrome.runtime.onMessage.addListener((m) => {
  if (m && m.type === 'reconnect') { retry = 0; connect(); }
  if (m && m.type === 'stop') {
    if (ws && ws.readyState === 1) { ws.send(JSON.stringify({ type: 'stop' })); stopped = true; chrome.action.setBadgeText({ text: '' }); setStatus('연결됨 · 조작 중지됨 (다음 작업부터 다시 조작)'); }
    else setStatus('연결 안 됨 — 중지할 작업이 없습니다');
  }
});
// 링크가 새 탭으로 열리면 그 탭을 이어서 조작한다
chrome.tabs.onCreated.addListener((t) => { if (agentTab !== null && t.openerTabId === agentTab) agentTab = t.id; });
connect();  // 서비스 워커가 (재)시작될 때마다 실행된다. 시작·설치 이벤트로 또 부르면 연결이 겹쳐 서로 끊는다

async function ensureTab() {
  if (agentTab !== null) { try { return await chrome.tabs.get(agentTab); } catch (_) { agentTab = null; } }
  const t = await chrome.tabs.create({ url: 'about:blank', active: true });
  agentTab = t.id;
  return t;
}
function waitComplete(tabId, ms = 25000) {
  return new Promise((resolve) => {
    const t = setTimeout(() => { chrome.tabs.onUpdated.removeListener(fn); resolve(false); }, ms);
    const fn = (id, info) => { if (id === tabId && info.status === 'complete') { clearTimeout(t); chrome.tabs.onUpdated.removeListener(fn); resolve(true); } };
    chrome.tabs.onUpdated.addListener(fn);
  });
}
async function snapshot(tabId) {
  for (let i = 0; i < 2; i++) {
    try {
      const [r] = await chrome.scripting.executeScript({ target: { tabId }, files: ['snap.js'] });
      const tab = await chrome.tabs.get(tabId);
      const s = r.result || { elements: [], text: '' };
      let text = s.text;
      try {
        const [d] = await chrome.scripting.executeScript({ target: { tabId }, func: () => { const a = JSON.parse(sessionStorage.getItem('__agentDialogs') || '[]'); sessionStorage.removeItem('__agentDialogs'); return a; } });
        if (d.result && d.result.length) text = '[페이지 대화상자 자동 응답] ' + d.result.slice(-3).join(' / ') + '\n' + text;
      } catch (_) {}
      if (urlHist[urlHist.length - 1] !== tab.url) urlHist.push(tab.url);
      sig = JSON.stringify([tab.url, (s.elements || []).length, s.text]);
      return { ok: true, url: tab.url, title: tab.title, elements: s.elements, text, sy: s.sy };
    } catch (e) { if (i) return { ok: false, error: '화면을 읽지 못했습니다: ' + e.message }; await sleep(600); }
  }
}
async function navigated(tabId, action) {
  const done = waitComplete(tabId);
  await action();
  await done; await sleep(1500);
  return snapshot(tabId);
}

async function handle(c) {
  if (c.cmd === 'close_tab') {  // 요청이 끝났다: 작업용 탭을 닫는다 (탭이 없으면 새로 열지 않고, 사용자가 직접 연 다른 탭은 건드리지 않는다)
    if (agentTab !== null) { try { await chrome.tabs.remove(agentTab); } catch (_) {} }
    agentTab = null; urlHist = []; sig = null;
    return { ok: true };
  }
  const tab = await ensureTab();
  switch (c.cmd) {
    case 'goto': return navigated(tab.id, () => chrome.tabs.update(tab.id, { url: c.url, active: true }));
    case 'snapshot': return snapshot(tab.id);
    case 'reload': return navigated(tab.id, () => chrome.tabs.reload(tab.id));
    case 'back': {
      const cur = (await chrome.tabs.get(tab.id)).url;
      const prev = [...urlHist].reverse().find((u, i, a) => i > a.indexOf(cur) && u !== cur) || urlHist[urlHist.length - 2];
      if (!prev) return { ok: false, error: '이전 페이지가 없습니다' };
      urlHist.pop();
      return navigated(tab.id, async () => { try { await chrome.tabs.goBack(tab.id); } catch (_) { await chrome.tabs.update(tab.id, { url: prev }); } });
    }
    case 'wait': await sleep(Math.min(Number(c.seconds) || 1, 10) * 1000); return snapshot(tab.id);
    case 'scroll': {
      const dir = c.direction || 'down';
      await chrome.scripting.executeScript({ target: { tabId: tab.id }, args: [dir], func: (d) => {
        if (d === 'top') scrollTo(0, 0); else if (d === 'bottom') scrollTo(0, document.body.scrollHeight);
        else scrollBy(0, innerHeight * 0.8 * (d === 'up' ? -1 : 1)); } });
      await sleep(300); return snapshot(tab.id);
    }
    case 'click': return click(tab, c);
    case 'type': return typeText(tab, c);
    case 'press': return press(tab, c);
    case 'select': return selectOption(tab, c);
    case 'frame': case 'screenshot': return frame(tab, c);
    default: return { ok: false, error: `확장이 '${c.cmd}' 명령을 아직 지원하지 않습니다` };
  }
}

const inPage = async (tabId, func, args = []) => {
  try { const [r] = await chrome.scripting.executeScript({ target: { tabId }, func, args }); return r.result; }
  catch (e) { return { err: e.message }; }
};
async function settleAfterAction(tab) {
  await sleep(700);
  try { const t = await chrome.tabs.get(tab.id); if (t.status === 'loading') await waitComplete(tab.id); } catch (_) {}
  await sleep(800);
}

async function click(tab, c) {
  const before = sig;
  await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['blocked.js'] });
  const r = await inPage(tab.id, (ref) => {
    const el = document.querySelector(`[data-agent-ref="${ref}"]`);
    if (!el) return { notfound: true };
    const blocked = globalThis.__agentBlocked ? globalThis.__agentBlocked(el) : '';
    if (blocked) return { blocked };
    const b = el.getBoundingClientRect(), x = b.x + b.width / 2, y = b.y + b.height / 2;
    const o = { bubbles: true, cancelable: true, composed: true, view: window, clientX: x, clientY: y, button: 0 };
    const tgt = document.elementFromPoint(x, y) || el;
    for (const t of ['pointerover', 'mouseover', 'pointermove', 'mousemove', 'pointerdown', 'mousedown']) tgt.dispatchEvent(new (t.startsWith('pointer') ? PointerEvent : MouseEvent)(t, o));
    if (el.focus) el.focus({ preventScroll: true });
    for (const t of ['pointerup', 'mouseup']) tgt.dispatchEvent(new (t.startsWith('pointer') ? PointerEvent : MouseEvent)(t, o));
    el.click();
    return { clicked: true };
  }, [Number(c.ref)]);
  if (!r || r.notfound || r.blocked || r.err) return { ok: false, notfound: r && r.notfound, blocked: r && r.blocked, error: r && r.err };
  await settleAfterAction(tab);
  let snap = await snapshot(tab.id);
  if (before !== null && sig === before) {  // 변화가 없다: 열리는 데 시간이 걸리는 화면일 수 있어 한 번 더 읽는다 (대화상자 안내는 잃지 않는다)
    const note = (snap.text || '').startsWith('[페이지 대화상자') ? snap.text.split('\n')[0] : '';
    await sleep(1200); snap = await snapshot(tab.id);
    if (note && !(snap.text || '').startsWith('[페이지 대화상자')) snap.text = note + '\n' + snap.text;
  }
  return snap;
}

async function typeText(tab, c) {
  const r = await inPage(tab.id, (ref, text) => {
    const el = document.querySelector(`[data-agent-ref="${ref}"]`);
    if (!el) return { notfound: true };
    el.scrollIntoView({ block: 'center' }); el.focus();
    if (el.select) el.select(); else if (el.isContentEditable) document.execCommand('selectAll');
    let ok = text ? document.execCommand('insertText', false, text) : document.execCommand('delete');
    if (!ok && 'value' in el) {  // execCommand 가 먹지 않는 입력칸: 값을 직접 넣고 입력 이벤트를 보낸다
      const set = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value')?.set;
      set ? set.call(el, text) : (el.value = text);
      el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true }));
    }
    return { ok: true, value: 'value' in el ? String(el.value).slice(0, 80) : '' };
  }, [Number(c.ref), String(c.text || '').slice(0, 2000)]);
  if (!r || r.notfound || r.err) return { ok: false, notfound: r && r.notfound, error: r && r.err };
  if (c.submit) return pressKey(tab, 'Enter');
  return { ok: true, url: (await chrome.tabs.get(tab.id)).url };
}

async function pressKey(tab, key) {
  const r = await inPage(tab.id, (key) => {
    const el = document.activeElement || document.body;
    const code = key.length === 1 ? (/[a-z]/i.test(key) ? 'Key' + key.toUpperCase() : key) : key;
    const ev = (t) => new KeyboardEvent(t, { key, code, bubbles: true, cancelable: true, composed: true });
    const down = el.dispatchEvent(ev('keydown'));  // false 면 페이지가 처리했다
    if (down) {
      if (key === 'Enter') {
        const form = el.closest && el.closest('form');
        if (el.tagName === 'A' || el.tagName === 'BUTTON' || el.getAttribute('role') === 'button') el.click();
        else if (form && el.tagName === 'INPUT') (form.requestSubmit ? form.requestSubmit() : form.submit());
      } else if (key === ' ' || key === 'Space') { if (el.tagName === 'BUTTON' || el.getAttribute('role') === 'button') el.click(); }
      else if (key === 'Backspace') document.execCommand('delete');
      else if (key === 'Delete') document.execCommand('forwardDelete');
      else if (key === 'Tab') {
        const f = [...document.querySelectorAll('a[href],button,input,select,textarea,[tabindex]')].filter((x) => !x.disabled && x.tabIndex >= 0 && x.offsetParent !== null);
        const i = f.indexOf(el); const n = f[(i + 1) % f.length]; if (n) n.focus();
      } else if (key.length === 1) document.execCommand('insertText', false, key);
    }
    el.dispatchEvent(ev('keyup'));
    return { ok: true };
  }, [key === 'Space' ? ' ' : key]);
  if (r && r.err) return { ok: false, error: r.err };
  await settleAfterAction(tab);
  return snapshot(tab.id);
}
const press = (tab, c) => pressKey(tab, String(c.key || 'Enter'));

async function selectOption(tab, c) {
  const r = await inPage(tab.id, (ref, want) => {
    const el = document.querySelector(`[data-agent-ref="${ref}"]`);
    if (!el || !el.options) return { ok: false };
    const o = [...el.options].find((o) => o.value === want || o.text.trim() === want);
    if (!o) return { ok: false };
    el.value = o.value;
    el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true }));
    return { ok: true };
  }, [Number(c.ref), String(c.text || '')]);
  return r && r.ok ? { ok: true } : { ok: false, error: '선택할 수 있는 항목을 찾지 못했습니다' };
}

async function frame(tab, c) {
  await chrome.tabs.update(tab.id, { active: true });
  const t = await chrome.tabs.get(tab.id);
  const url = await chrome.tabs.captureVisibleTab(t.windowId, c.cmd === 'frame' ? { format: 'jpeg', quality: Number(c.quality) || 55 } : { format: 'png' });
  return { ok: true, img: url.split(',')[1], url: t.url, title: t.title };
}
