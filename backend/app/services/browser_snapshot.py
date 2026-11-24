"""브라우저 화면 요소 수집 스크립트 (sandbox 데몬과 데스크톱 로컬 브라우저가 같은 것을 쓴다).

눌러 볼 수 있는 요소에 data-agent-ref 번호를 매겨 목록으로 돌려준다. 수집 대상:
- 시맨틱 요소: a/button/input/select/textarea/summary, role=button·link·checkbox·tab·menuitem*·option·radio·switch·combobox·treeitem, onclick
- 시맨틱 표시는 없지만 눌리는 요소(커서가 pointer 인 작은 div/li/span 등): 커스텀 드롭다운의 항목이 대표적이다
요소가 상한을 넘으면 열려 있는 팝업(listbox·dialog·menu·모달·드롭다운)·방금 새로 나타난 요소 → 지금 화면의 버튼·입력칸 등 → 지금 화면의 링크 → 지금 화면의 커서만 pointer 인 일반 요소 → 나머지 순으로 담는다: 팝업은 DOM 맨 끝에 붙는 일이 많아 잘리기 쉽고, 목록 화면에서는 줄마다 반복되는 요소가 상한을 채워 조작 요소나 메일 제목 링크가 잘리기 쉽다.
본문에서 취소선이 그어진 글자(이전 가격 등)는 ~~글자~~ 로 표시한다.
이름이 없는 요소에는 무엇인지 알 수 있는 단서(label ← 아이콘 제목·연결 라벨, tid ← data-testid 류, ctx ← 가까운 짧은 영역의 글자, cls ← 의미 있는 class 단어)를 붙인다.
"""

SNAP_JS = r"""(() => {
  const MAX = 160;
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
    // 버튼 모양의 링크(class 에 btn·button·tab)와 탭(role=tab)은 버튼처럼 앞에 둔다: 메가박스의 '극장별' 탭은 <a class="btn"> 이라 영화 포스터 버튼 수십 개에 밀려 목록에서 잘렸다
    const btnLike = (el) => el.tagName === 'A' && (el.getAttribute('role') === 'tab' || /(^|[\s_-])(btn|button|tab)([\s_-]|$)/i.test(typeof el.className === 'string' ? el.className : ''));
    // 같은 모양(태그+class)이 40개를 넘는 반복 목록(터미널·영화·상품 줄)은 한 단계 뒤로: 목록 항목 수백 개가 같은 팝업의 '선택완료'·'확인' 버튼을 상한 밖으로 밀어내지 않게 한다
    const groupCount = new Map(); const gk = (el) => el.tagName + '.' + (typeof el.className === 'string' ? el.className : '');
    for (const el of cands) groupCount.set(gk(el), (groupCount.get(gk(el)) || 0) + 1);
    const bulk = (el) => groupCount.get(gk(el)) > 40;
    const rank = (el) => (bare(el) || generic(el)) ? 2 : Math.min(2, ((el.tagName === 'A' && !btnLike(el)) ? 1 : 0) + (bulk(el) ? 1 : 0));
    // 화면 안인데 그 자리에서 눌리는 것이 다른 요소인 항목(슬라이더 밖으로 밀려난 항목, 다른 요소에 가려진 항목)은 팝업 안에서도 뒤로 민다
    const covered = (el) => { const r = el.getBoundingClientRect(); const cx = r.x + r.width / 2, cy = r.y + r.height / 2;
      if (cx < 0 || cy < 0 || cx > innerWidth || cy > innerHeight) return false;
      const h = document.elementFromPoint(cx, cy); if (!h || h === el || el.contains(h) || h.contains(el)) return false;
      const q = 'a,button,label,summary,[role=button],[onclick]'; const h1 = h.closest(q); return !(h1 && h1 === el.closest(q)); };
    const g = [0, 1, 2].map(r => new Set(view.filter(el => rank(el) === r)));
    picked = cands.filter(el => isPop.has(el)).map(el => [el, rank(el) + (covered(el) ? 3 : 0)]).sort((a, b) => a[1] - b[1]).map(x => x[0]).concat(cands.filter(el => g[0].has(el)), cands.filter(el => g[1].has(el)), cands.filter(el => g[2].has(el)), cands.filter(el => !isPop.has(el) && !view.includes(el))).slice(0, isPop.size > 60 ? MAX + 50 : MAX);   // 팝업(달력+시간 슬라이더 등)이 크면 상한을 조금 늘려 팝업 안 요소가 잘리지 않게 한다
    picked.sort((a, b) => a === b ? 0 : (a.compareDocumentPosition(b) & 4 ? -1 : 1));   // 번호는 문서 순서로 다시 매긴다
  }

  const STOP = new Set(['react', 'border', 'outline', 'flex', 'btn', 'button', 'css', 'item', 'wrapper', 'container', 'active', 'hover', 'focus', 'rounded', 'text', 'icon', 'inline', 'block', 'relative', 'absolute', 'svg', 'sc', 'jsx', 'styled', 'component', 'base', 'default', 'primary', 'secondary', 'small', 'large', 'medium', 'full', 'width', 'center', 'with', 'for', 'the']);
  const out = []; const outEls = []; let n = 0;
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
    // 달력 칸처럼 이름은 '4' 뿐인데 날짜를 속성으로 갖는 요소: 같은 숫자가 여러 달에 반복돼도 어느 날짜인지 알 수 있게 한다 (Google Flights 의 data-iso)
    const dateAttr = el.getAttribute('data-iso') || el.getAttribute('data-date') || el.getAttribute('data-day') || el.getAttribute('datetime');
    if (dateAttr && /^\d{4}-\d{2}-\d{2}/.test(dateAttr)) item.date = dateAttr.slice(0, 10);
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
    const ttl = (el.getAttribute('title') || '').trim();   // aria 대신 title="선택됨" 으로 선택 상태를 알리는 사이트(CGV 날짜·극장·시간대 버튼)
    if (aSel === 'true' || /^(선택됨|선택된 항목|현재 선택됨?)$/.test(ttl)) item.sel = 'selected'; else if (aCur && aCur !== 'false') item.sel = 'current';
    if (el.getAttribute('aria-pressed') === 'true') item.pressed = true;
    if (el.getAttribute('aria-expanded') === 'true') item.expanded = true;
    out.push(item); outEls.push(el);
  }
  // 같은 이름의 요소가 여럿이면(슬라이더마다 있는 'Next'·'Previous' 화살표, 줄마다 있는 '선택' 버튼 등) 어느 것인지 알 수 있게 순번과 맥락을 붙인다:
  // 이름만 보고 누르면 엉뚱한 쪽(예: 달력의 월 이동)이 눌려 목표(시각 슬라이더 이동)가 이뤄지지 않는다
  const byLabel = new Map();
  out.forEach((it, i) => { if (it.label) { const k = it.tag + '|' + it.label; (byLabel.get(k) || byLabel.set(k, []).get(k)).push(i); } });
  const HEAD = 'h1,h2,h3,h4,h5,caption,legend,strong,[class*=title i],[class*=tit i],[class*=month i],[class*=head i]';
  for (const idxs of byLabel.values()) {
    if (idxs.length < 2) continue;
    // 맥락: 가까운 조상 안의 제목(월 머리글·'시간선택' 같은 구역 이름). 같은 칸의 이웃 항목 글자(1 2 3 …)는 구분에 도움이 안 된다.
    // 같은 이름 요소 모두에 똑같이 붙는 제목('달력')보다 서로 달라지는 제목('2026. 11.')을 우선한다
    const heads = idxs.map(i => { const el = outEls[i], hs = [];
      for (let a = el.parentElement, n = 0; a && n < 6 && a !== document.body; a = a.parentElement, n++) {
        for (const x of a.querySelectorAll(HEAD)) { if (x === el || el.contains(x) || x.contains(el)) continue; const t = clean(x.innerText, 30); if (t && t !== out[i].label && !hs.includes(t)) hs.push(t); }
      }
      return hs; });
    idxs.forEach((i, k) => {
      const it = out[i]; it.dup = (k + 1) + '/' + idxs.length;
      if (it.ctx) return;
      const own = heads[k], pick = own.find(t => heads.some(h => !h.includes(t))) || own[0];
      if (pick) it.ctx = pick;
    });
  }
  // 페이지 본문: 취소선이 그어진 글자(이전 가격 등)는 ~~글자~~ 로 표시한다. innerText 는 서식을 잃어서 취소선 가격과 현재 가격이 구분되지 않기 때문이다
  let txt = (document.body ? document.body.innerText : '').slice(0, 8000);
  // 본문이 길면(왼쪽 필터·메뉴가 앞부분을 다 차지하는 목록 화면 등) 앞 3000자에 정작 보이는 내용이 없다. 그때는 지금 화면에 보이는 글자를 본문으로 쓴다.
  if (txt.length > 2800 && document.body) {
    try {
      const vis = []; let len = 0;
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {acceptNode: (n) => {
        const p = n.parentElement; if (!p || ['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(p.tagName) || !n.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT; }});
      const range = document.createRange(); let scanned = 0;
      while (walker.nextNode() && len < 6000 && ++scanned < 20000) {
        const n = walker.currentNode; range.selectNodeContents(n);
        const r = range.getBoundingClientRect();
        if (r.width < 1 || r.height < 1 || r.bottom <= 0 || r.top >= window.innerHeight || r.right <= 0 || r.left >= window.innerWidth) continue;
        const st = getComputedStyle(n.parentElement); if (st.visibility === 'hidden' || st.display === 'none') continue;
        const t = n.nodeValue.trim().replace(/\s+/g, ' '); vis.push(t); len += t.length + 1;
      }
      const v = vis.join('\n');
      if (v.length >= 200) txt = v.slice(0, 8000);
    } catch (e) {}
  }
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


# 누르기 전에 그 요소 자리에서 실제로 눌리는 것이 이 요소(또는 같은 눌림 대상)인지 확인한다. 아니면 그 자리의 다른 요소 이름을 돌려주고(빈 문자열이면 정상),
# 슬라이더 밖으로 밀려나 보이지 않는 항목을 눌러 엉뚱한 항목(예: 09시 대신 18시)이 선택되는데도 성공으로 보이는 것을 막는다.
BLOCKED_JS = r"""(el) => {
  // 같은 슬라이더의 화살표 버튼 이름: 숨은 항목은 이 화살표로 넘겨야 보인다
  const arrows = () => { for (let a = el.parentElement, n = 0; a && n < 6 && a !== document.body; a = a.parentElement, n++) {
      const bs = [...a.querySelectorAll('button,a')].filter(x => x !== el && /next|prev|다음|이전/i.test((x.className || '') + ' ' + (x.getAttribute('aria-label') || '') + ' ' + (x.innerText || '')));
      if (bs.length && el.closest('[class*=slick i],[class*=swiper i],[class*=carousel i],[class*=slider i]')) return ' 같은 슬라이더의 화살표 버튼: ' + bs.slice(0, 2).map(x => '“' + ((x.innerText || x.getAttribute('aria-label') || x.className || '').trim().slice(0, 20)) + '”').join(', ') + ' (이름이 같은 것이 여럿이면 순번·맥락으로 구분)'; }
    return ''; };
  if (el.getAttribute('aria-disabled') === 'true' || el.disabled) return '비활성 상태(aria-disabled)입니다. 이미 지난 날짜·시각이거나 슬라이더 안에 숨은 항목일 수 있습니다.' + arrows();
  el.scrollIntoView({block: 'center', inline: 'nearest'});   // 가로로도 스크롤되는 페이지(롯데시네마)에서 가운데 맞춤은 화면을 옆으로 밀어 엉뚱한 요소가 가리게 된다
  const r = el.getBoundingClientRect(); const cx = r.x + r.width / 2, cy = r.y + r.height / 2;
  const hit = document.elementFromPoint(cx, cy);
  if (!hit) return '';   // 화면 밖이라 판단할 수 없다
  const q = 'a,button,label,summary,[role=button],[onclick]'; const h1 = hit.closest(q), e1 = el.closest(q);
  // 이 요소이거나 그 안쪽, 또는 같은 눌림 대상(버튼 안의 글자 등)이면 정상. 이 요소를 감싼 일반 영역(슬라이더 틀 등)이 맨 위에 있으면 이 요소는 가려진 것이다
  if (hit === el || el.contains(hit) || (h1 && h1 === e1) || (hit.contains(el) && hit.matches(q))) return '';
  return '그 자리에는 다른 요소(' + (((hit.tagName || '') + ' ' + (hit.innerText || hit.getAttribute('aria-label') || '')).trim().replace(/\s+/g, ' ').slice(0, 30) || hit.tagName) + ')가 있습니다.' + arrows();
}"""

BLOCKED_MSG = ("ref {ref} 요소를 누를 수 없습니다: {what}. 가려졌거나 화면에 보이지 않는 요소입니다. 슬라이더 안의 항목이면 같은 슬라이더의 다음/이전 화살표로 넘긴 뒤 snapshot 으로 다시 확인하세요. "
               "그 밖에는 이 단계가 꼭 필요한지 확인하세요(예: '적용' 버튼이 가려도 다음 단계를 바로 눌러 반영되는 화면이 있습니다). 같은 이름의 다른 요소가 있으면 그것을 누르세요.")

# 화면 본문에 이 문구가 보이면 아직 불러오는 중이다(CGV '잠시만 기다려 주세요.' 는 위젯이 약 6초 뒤에 뜬다, Google Flights '결과를 가져오는 중'). 읽기 전에 잠시 기다린다.
LOADING_PATTERN = r"잠시만 기다려|로딩 ?중|불러오는 중|가져오는 중|Loading\.\.\."
LOADING_WAIT_SECONDS = 6
