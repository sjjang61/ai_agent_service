(() => {
  if (window.__agentDialogsInstalled) return; window.__agentDialogsInstalled = true;
  const OK = new RegExp("(\ucde8\uc18c\\s*)?\uc218\uc218\ub8cc[^\\n]{0,20}(\ub0b4\uc6a9|\uc548\ub0b4|\uaddc\uc815)[^\\n]{0,20}\ub3d9\uc758|(\uc774\uc6a9|\uc720\uc758|\uc548\ub0b4|\uc6b4\ud589)\\s*(\uc548\ub0b4|\uc0ac\ud56d|\uc2dc\uac04)[^\\n]{0,20}(\ud655\uc778|\ub3d9\uc758)\ud558(\uc2ed\ub2c8\uae4c|\uc2dc\uaca0\uc2b5\ub2c8\uae4c)"), DENY = new RegExp("\uacb0\uc81c|\uad6c\ub9e4|\uc0ad\uc81c|\ud0c8\ud1f4|\uc8fc\ubb38|\uc1a1\uae08|\uc774\uccb4|\uc2e0\uccad|\uc608\uc57d\uc744 (\ud655\uc815|\uc9c4\ud589)|\uc608\ub9e4\ub97c (\ud655\uc815|\uc9c4\ud589)|\ucde8\uc18c\ud558\uc2dc\uaca0|\ud658\ubd88\ud558\uc2dc\uaca0|\ub85c\uadf8\uc544\uc6c3");
  const rec = (s) => { try { const a = JSON.parse(sessionStorage.getItem('__agentDialogs') || '[]'); a.push(String(s).slice(0, 240)); sessionStorage.setItem('__agentDialogs', JSON.stringify(a.slice(-5))); } catch (_) {} };
  window.alert = (m) => { rec('확인 처리한 alert 대화상자: ' + m); };
  window.confirm = (m) => { m = String(m == null ? '' : m); const ok = OK.test(m) && !DENY.test(m); rec((ok ? '확인' : '취소') + ' 처리한 confirm 대화상자: ' + m); return ok; };
  window.prompt = (m) => { rec('취소 처리한 prompt 대화상자: ' + m); return null; };
})();
