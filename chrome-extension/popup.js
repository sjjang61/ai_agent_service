const $ = (id) => document.getElementById(id);
chrome.storage.local.get(['server', 'token', 'status'], (v) => {
  if (v.server) $('server').value = v.server;
  if (v.token) $('token').value = v.token;
  $('st').textContent = '연결 상태: ' + (v.status || '연결 안 됨');
});
chrome.storage.onChanged.addListener((c) => { if (c.status) $('st').textContent = '연결 상태: ' + c.status.newValue; });
$('save').onclick = () => {
  chrome.storage.local.set({ server: $('server').value.trim(), token: $('token').value.trim() }, () => chrome.runtime.sendMessage({ type: 'reconnect' }));
};

$('stop').onclick = () => { chrome.runtime.sendMessage({ type: 'stop' }); $('stop').textContent = '중지 요청함'; setTimeout(() => { $('stop').textContent = '조작 중지'; }, 2500); };
