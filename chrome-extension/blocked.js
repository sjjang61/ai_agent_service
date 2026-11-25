globalThis.__agentBlocked = (el) => {
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
};
