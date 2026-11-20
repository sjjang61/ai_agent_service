"""브라우저 화면 요소 수집 스크립트 (sandbox 데몬과 데스크톱 로컬 브라우저가 같은 것을 쓴다).

눌러 볼 수 있는 요소에 data-agent-ref 번호를 매겨 목록으로 돌려준다. 수집 대상:
- 시맨틱 요소: a/button/input/select/textarea/summary, role=button·link·checkbox·tab·menuitem*·option·radio·switch·combobox·treeitem, onclick
- 시맨틱 표시는 없지만 눌리는 요소(커서가 pointer 인 작은 div/li/span 등): 커스텀 드롭다운의 항목이 대표적이다
요소가 상한을 넘으면 열려 있는 팝업(listbox·dialog·menu·모달·드롭다운)·방금 새로 나타난 요소 → 지금 화면의 버튼·입력칸 등 → 지금 화면의 링크 → 지금 화면의 커서만 pointer 인 일반 요소 → 나머지 순으로 담는다: 팝업은 DOM 맨 끝에 붙는 일이 많아 잘리기 쉽고, 목록 화면에서는 줄마다 반복되는 요소가 상한을 채워 조작 요소나 메일 제목 링크가 잘리기 쉽다.
본문에서 취소선이 그어진 글자(이전 가격 등)는 ~~글자~~ 로 표시한다.
이름이 없는 요소에는 무엇인지 알 수 있는 단서(label ← 아이콘 제목·연결 라벨, tid ← data-testid 류, ctx ← 가까운 짧은 영역의 글자, cls ← 의미 있는 class 단어)를 붙인다.
"""

SNAP_JS = r"""(() => {
  const MAX = 120;
  const sel = 'a[href],button,input,select,textarea,summary,[role=button],[role=link],[role=checkbox],[role=tab],[role=menuitem],[role=menuitemradio],[role=menuitemcheckbox],[role=option],[role=radio],[role=switch],[role=combobox],[role=treeitem],[onclick]';
  const overlaySel = '[role=listbox],[role=dialog],[role=alertdialog],[role=menu],[aria-modal=true],[class*=popup i],[class*=popover i],[class*=dropdown i],[class*=modal i],[class*=listbox i]';
  document.querySelectorAll('[data-agent-ref]').forEach(e => e.removeAttribute('data-agent-ref'));
  const visible = (el) => {
    const r = el.getBoundingClientRect(); const st = getComputedStyle(el);
    return !(r.width < 2 || r.height < 2 || st.visibility === 'hidden' || st.display === 'none' || el.type === 'hidden');
  };
  const clean = (s, n) => String(s || '').trim().replace(/\s+/g, ' ').slice(0, n);

  const cands = []; const seen = new Set();
  for (const el of document.querySelectorAll(sel)) if (visible(el)) { cands.push(el); seen.add(el); }

  // 시맨틱 표시는 없지만 눌리는 요소: 커서가 pointer 인 작은 요소 (바깥쪽 하나만: 커서는 자식에게 상속된다)
  const extra = []; let scanned = 0;
  for (const el of document.querySelectorAll('div,li,span,label,td,p')) {
    if (seen.has(el) || ++scanned > 4000 || el.children.length > 3) continue;
    const txt = clean(el.innerText, 80);
    if (!txt || txt.length > 60 || getComputedStyle(el).cursor !== 'pointer' || el.closest(sel) || !visible(el)) continue;
    extra.push(el);
  }
  for (const el of extra) if (!extra.some(a => a !== el && a.contains(el))) { cands.push(el); seen.add(el); }

  cands.sort((a, b) => a === b ? 0 : (a.compareDocumentPosition(b) & 4 ? -1 : 1));   // 문서 순서
  // 직전 수집 이후 새로 나타난 요소(방금 눌러서 열린 패널·메뉴): 소수일 때만 팝업처럼 앞에 두고, 이후 3번의 수집까지 유지한다
  // (누른 직후의 결과와 그다음 snapshot 에서 같은 요소가 보이도록). 화면 전체가 바뀐 경우(이동)에는 모두 새것이라 쓰지 않는다
  const prev = window.__agentSeen; const ttl = window.__agentFresh || new Map();
  for (const [el, t] of [...ttl]) { if (!el.isConnected || t <= 1) ttl.delete(el); else ttl.set(el, t - 1); }
  if (prev) {
    const added = cands.filter(el => !prev.has(el));
    if (added.length <= 40) for (const el of added) ttl.set(el, 3);
  }
  const fresh = new Set(cands.filter(el => ttl.has(el)));
  window.__agentSeen = new WeakSet(cands); window.__agentFresh = ttl;
  let picked = cands;
  if (cands.length > MAX) {   // 상한을 넘으면 열린 팝업·방금 나타난 요소 → 지금 화면의 버튼·입력칸 등 → 지금 화면의 링크 → 일반 요소 → 나머지 순으로 담는다.
    const isPop = new Set(cands.filter(el => el.closest(overlaySel) || fresh.has(el)));
    const onScreen = (el) => { const r = el.getBoundingClientRect(); return r.bottom > 0 && r.top < window.innerHeight; };
    const view = cands.filter(el => !isPop.has(el) && onScreen(el));
    // 이름 없는 체크박스(목록 줄마다 하나씩 있는 선택 칸)와 시맨틱 표시 없이 커서만 pointer 인 일반 요소(div·span·li 등)는 수십~수백 개일 수 있어서 맨 뒤로 둔다
    const bare = (el) => el.tagName === 'INPUT' && el.type === 'checkbox' && !el.getAttribute('aria-label') && !el.title && !(el.labels && el.labels.length);
    const generic = (el) => !['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'SUMMARY'].includes(el.tagName) && !el.getAttribute('role') && !el.hasAttribute('onclick');
    const rank = (el) => (bare(el) || generic(el)) ? 2 : el.tagName === 'A' ? 1 : 0;
    const g = [0, 1, 2].map(r => new Set(view.filter(el => rank(el) === r)));
    picked = cands.filter(el => isPop.has(el)).concat(cands.filter(el => g[0].has(el)), cands.filter(el => g[1].has(el)), cands.filter(el => g[2].has(el)), cands.filter(el => !isPop.has(el) && !view.includes(el))).slice(0, MAX);
    picked.sort((a, b) => a === b ? 0 : (a.compareDocumentPosition(b) & 4 ? -1 : 1));   // 번호는 문서 순서로 다시 매긴다
  }

  const STOP = new Set(['react', 'border', 'outline', 'flex', 'btn', 'button', 'css', 'item', 'wrapper', 'container', 'active', 'hover', 'focus', 'rounded', 'text', 'icon', 'inline', 'block', 'relative', 'absolute', 'svg', 'sc', 'jsx', 'styled', 'component', 'base', 'default', 'primary', 'secondary', 'small', 'large', 'medium', 'full', 'width', 'center', 'with', 'for', 'the']);
  const out = []; let n = 0;
  for (const el of picked) {
    n++; el.setAttribute('data-agent-ref', String(n));
    const label = clean(el.innerText || el.value || el.getAttribute('aria-label') || el.placeholder || el.title || el.alt, 80);
    const item = {ref: n, tag: el.tagName.toLowerCase(), label};
    if (el.type && el.tagName !== 'BUTTON' && el.tagName !== 'A') item.type = el.type;
    if (el.getAttribute('role')) item.role = el.getAttribute('role');
    if (el.name) item.name = el.name;
    if (el.placeholder) item.placeholder = el.placeholder;
    if (el.value && el.type !== 'password' && el.tagName !== 'BUTTON') item.value = String(el.value).slice(0, 60);
    if (el.href) item.href = el.href.slice(0, 120);
    if (el.checked) item.checked = true;
    if (el.disabled) item.disabled = true;
    if (!item.label) {   // 이름 없는 요소(아이콘 버튼 등): 무엇인지 알 수 있는 단서를 붙인다
      const t = el.querySelector('svg title, img[alt]');
      const lb = el.getAttribute('aria-labelledby');
      const own = clean((t && (t.textContent || t.alt)) || (lb && (document.getElementById(lb) || {}).innerText), 40);
      if (own) item.label = own;
      else {
        let tid = '';
        for (const a of ['data-testid', 'data-test-id', 'data-test', 'data-selenium', 'data-element-name', 'data-cy', 'data-qa']) {
          const v = el.getAttribute(a); if (v) { tid = v; break; }
        }
        if (!tid && el.id && /[a-zA-Z]{3,}/.test(el.id) && !/\d{4,}/.test(el.id)) tid = el.id;
        if (tid) item.tid = clean(tid, 40);
        // 맥락: 가까운 조상 중 글자가 짧은(80자 이하) 첫 영역. 페이지 전체를 감싸는 큰 영역의 첫 글자(배너 등)는 쓰지 않는다
        let ctx = '';
        for (let a = el.parentElement, i = 0; a && i < 5 && a !== document.body; a = a.parentElement, i++) {
          const tx = clean(a.innerText, 200);
          if (tx && tx.length <= 80) { ctx = tx; break; }
        }
        if (!ctx) { const prev = el.previousElementSibling; ctx = prev ? clean(prev.innerText || prev.getAttribute('aria-label'), 40) : ''; }
        if (ctx) item.ctx = ctx.slice(0, 40);
        const words = ((typeof el.className === 'string' ? el.className : '')).split(/[\s_\-]+/).filter(w => /^[a-zA-Z]{3,}$/.test(w) && !STOP.has(w.toLowerCase())).slice(0, 3).join(' ');
        if (words) item.cls = words.slice(0, 30);
      }
    }
    const aSel = el.getAttribute('aria-selected'), aCur = el.getAttribute('aria-current');   // 이미 선택된 항목(날짜·탭 등)을 구분할 수 있게 상태를 알린다
    if (aSel === 'true') item.sel = 'selected'; else if (aCur && aCur !== 'false') item.sel = 'current';
    if (el.getAttribute('aria-pressed') === 'true') item.pressed = true;
    if (el.getAttribute('aria-expanded') === 'true') item.expanded = true;
    out.push(item);
  }
  // 페이지 본문: 취소선이 그어진 글자(이전 가격 등)는 ~~글자~~ 로 표시한다. innerText 는 서식을 잃어서 취소선 가격과 현재 가격이 구분되지 않기 때문이다
  let txt = (document.body ? document.body.innerText : '').slice(0, 8000);
  try {
    const struck = []; let scanned = 0;
    for (const el of document.body ? document.body.querySelectorAll('*') : []) {
      if (++scanned > 5000) break;
      const tag = el.tagName;
      if (tag === 'SCRIPT' || tag === 'STYLE') continue;
      const dec = getComputedStyle(el).textDecorationLine || '';
      if (!(dec.includes('line-through') || tag === 'S' || tag === 'DEL' || tag === 'STRIKE')) continue;
      if (el.parentElement && (getComputedStyle(el.parentElement).textDecorationLine || '').includes('line-through')) continue;   // 바깥쪽 하나만
      const t = (el.innerText || '').trim();
      if (t && t.length <= 40 && !t.includes('\n') && visible(el)) struck.push(t);
    }
    let cur = 0;
    for (const t of struck.slice(0, 30)) {   // 문서 순서대로 본문에서 찾아 표시한다
      const i = txt.indexOf(t, cur);
      if (i >= 0) { txt = txt.slice(0, i) + '~~' + t + '~~' + txt.slice(i + t.length); cur = i + t.length + 4; }
    }
  } catch (e) {}
  return {elements: out, text: txt.slice(0, 3000), sy: Math.round(window.scrollY / Math.max(1, window.innerHeight / 2))};   // sy: 스크롤 위치(반 화면 단위) — 스크린샷 중복 판단용
})()"""
