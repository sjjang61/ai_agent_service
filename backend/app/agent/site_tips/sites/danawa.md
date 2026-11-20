---
name: 다나와
domains: danawa.com
vertical: shopping
aliases: 다나와
verified: 2026-11-09
---
```spec
{
  "entry": [
    {
      "label": "검색 결과",
      "url": "https://search.danawa.com/dsearch.php?query={query}"
    }
  ],
  "inputs": {
    "query": {
      "how": "주소의 query 파라미터에 넣습니다. 홈의 검색창에 입력 후 Enter 를 치면 결과 화면이 아니라 홈에 머물 수 있습니다.",
      "param": "query"
    },
    "sort": {
      "how": "결과 화면의 '낮은가격순' 버튼을 누르거나 주소 끝에 &sort=priceASC 를 붙입니다.",
      "param": "sort"
    }
  },
  "flow": [
    {
      "key": "search",
      "how": "검색 결과 주소로 바로 이동합니다.",
      "url": "https://search.danawa.com/dsearch.php?query={query}"
    },
    {
      "key": "sort",
      "how": "'낮은가격순' 버튼 또는 &sort=priceASC",
      "url": ""
    }
  ]
}
```
