---
name: 네이버 가격비교
domains: shopping.naver.com
vertical: shopping
aliases: 네이버 가격비교, 네이버가격비교, 네이버 쇼핑, 네이버쇼핑
status: draft
verified:
---
```spec
{
  "entry": [
    {
      "label": "검색 결과",
      "url": "https://search.shopping.naver.com/search/all?query={query}"
    }
  ],
  "inputs": {
    "query": {
      "how": "주소의 query 파라미터에 검색어를 URL 인코딩해 넣는다 (예: 맥심 → query=%EB%A7%A5%EC%8B%AC).",
      "param": "query"
    }
  }
}
```
