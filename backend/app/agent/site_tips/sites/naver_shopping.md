---
name: 네이버 가격비교
domains: shopping.naver.com
vertical: shopping
aliases: 네이버 가격비교, 네이버가격비교, 네이버 쇼핑, 네이버쇼핑
verified: 2026-11-20
---
```spec
{
  "flow": [
    {
      "how": "검색 결과 주소로 직접 이동한다.",
      "key": "search",
      "url": "https://search.shopping.naver.com/ns/search?query={query}"
    },
    {
      "how": "'낮은가격순' 정렬을 선택하면 sort=LOW_PRICE 가 적용된다.",
      "key": "sort",
      "url": "https://search.shopping.naver.com/ns/search?query={query}&sort=LOW_PRICE"
    },
    {
      "how": "검색 결과 목록의 상품 행에서 상품명, 상품가, 배송비, 판매처(스토어) 이름을 읽는다. 배송비는 행마다 따로 표시되므로 더해서 총액으로 비교한다.",
      "key": "compare",
      "url": ""
    },
    {
      "how": "상품 링크는 판매처 스토어(smartstore.naver.com)로 이동하며 네이버 보안 확인(CAPTCHA)이 표시된다. 상세는 열지 말고 목록 정보(상품명·가격·배송비·판매처)로 답한다. 상세 값이 꼭 필요하면 사용자에게 보안 확인을 통과해 달라고 요청한다.",
      "key": "detail",
      "url": "",
      "skip": true
    }
  ],
  "entry": [
    {
      "url": "https://search.shopping.naver.com/ns/search?query={query}",
      "label": "검색 결과"
    }
  ],
  "menus": [
    {
      "url": "https://shopping.naver.com/ns/home",
      "name": "검색",
      "path": "상단 검색영역"
    }
  ],
  "inputs": {
    "sort": {
      "how": "검색 결과의 정렬 옵션에서 '낮은가격순'을 누르면 주소에 sort=LOW_PRICE 가 추가된다 (주소로 직접 지정도 가능). 화면에 '낮은 가격순 선택됨'이 표시된다.",
      "param": "sort"
    },
    "query": {
      "how": "주소의 query 파라미터에 검색어를 URL 인코딩해 넣어 직접 이동한다. 쇼핑 홈의 상단 검색창에 입력하고 검색을 눌러도 같은 결과 주소로 이동한다.",
      "param": "query"
    }
  },
  "stop_point": "검색 결과 목록 화면에서 멈춥니다. 상품 링크(판매처 스토어에서 보안 확인이 뜹니다)와 '네이버 가격비교 검색에서 더보기' 링크는 누르지 않습니다 (더보기는 기존 경로로 전환되어 접속 제한 화면이 나옵니다)."
}
```

기존 형식 주소(`/search/all?query=…`)는 '쇼핑 서비스 접속이 일시적으로 제한되었습니다.' 화면이 나온다 (앱 브라우저와 일반 Chrome 모두에서 확인). 검색 결과는 `/ns/search?query={query}` 로 열린다.
'네이버 가격비교 검색에서 더보기' 링크를 누르면 기존 경로로 전환되어 접속 제한 화면이 나온다. 이 링크는 누르지 않는다.
상품 링크는 판매처 스토어(`smartstore.naver.com/main/products/…`)로 이동하며 네이버 보안 확인(CAPTCHA)이 표시된다. CAPTCHA 는 풀거나 우회하지 않는다.
최저가순 목록 위쪽에 규격·맛이 다른 상품(예: 약간매운맛)이 섞여 나온다. 요청한 규격과 다른 행은 비교에서 뺀다.
여러 수량 옵션(1·5·10…개입)이 한 행에 묶인 상품은 목록에 보이는 가격이 어느 옵션의 가격인지 알 수 없다. 5개입 가격으로 확정하지 않는다.
목록의 순서와 가격은 실행마다 달라진다 (광고·노출 순서).
