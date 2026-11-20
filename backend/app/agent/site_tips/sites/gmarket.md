---
name: 지마켓
domains: gmarket.co.kr
vertical: shopping
aliases: 지마켓, g마켓
verified: 2026-11-09
---
```spec
{
  "flow": [
    {
      "how": "검색 결과 주소로 바로 이동합니다. '잠시만 기다리십시오' 화면이면 몇 초 기다린 뒤 다시 확인하고, 계속되면 보안 확인으로 보고 사용자에게 넘기세요.",
      "key": "search",
      "url": "https://www.gmarket.co.kr/n/search?keyword={query}"
    }
  ],
  "entry": [
    {
      "url": "https://www.gmarket.co.kr/n/search?keyword={query}",
      "label": "검색 결과"
    }
  ],
  "menus": [],
  "inputs": {
    "query": {
      "how": "주소의 keyword 파라미터에 넣습니다.",
      "param": "keyword"
    }
  },
  "stop_point": ""
}
```

검색은 `https://www.gmarket.co.kr/n/search?keyword=검색어` 로 이동하세요.
"잠시만 기다리십시오" 화면이면 몇 초 기다린 뒤 snapshot 을 다시 찍고, 계속되면 보안 확인으로 보고 `request_user_login` 을 호출하세요.
