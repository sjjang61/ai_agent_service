---
name: 다나와
domains: danawa.com
vertical: shopping
aliases: 다나와
verified: 2026-11-20
---
```spec
{
  "flow": [
    {
      "how": "https://search.danawa.com/?query={query} 주소로 이동합니다. 결과 상단에는 별도 '이런 상품 어때요? 광고' 영역이 먼저 표시될 수 있습니다.",
      "key": "search",
      "url": "https://search.danawa.com/?query={query}"
    },
    {
      "how": "검색 결과 화면의 '낮은가격순'을 선택합니다. 최소 주소 형식은 https://search.danawa.com/?query={query}&sort=priceASC 이며 직접 열어 적용을 확인했습니다.",
      "key": "sort",
      "url": "https://search.danawa.com/?query={query}&sort=priceASC"
    },
    {
      "how": "광고 영역을 제외하고 같은 규격의 일반 검색 결과를 엽니다. 상품 상세의 '다른 구성'에서 구성별 최저가·개당 가격·판매처 수를 확인하고, '가격비교' 탭의 판매처 행에서 상품가와 배송비를 비교합니다.",
      "key": "compare",
      "url": ""
    },
    {
      "how": "검색 결과의 상품명을 열면 상품 상세로 이동합니다. 확인한 상품은 '오뚜기 진라면 순한맛 120g (5개)'이며, 상세의 표시 가격은 전체 최저가이고 '가격비교' 탭에는 판매처별 상품가·배송비·구매하기 링크가 표시됩니다. 판매처명, 가격, 상품명 및 '구매하기'는 다나와 내부 /bridge/loadingBridge.html 경유 링크입니다.",
      "key": "detail",
      "url": "https://prod.danawa.com/info/?pcode=1239445"
    }
  ],
  "entry": [
    {
      "url": "https://search.danawa.com/?query={query}",
      "label": "검색 결과"
    }
  ],
  "menus": [
    {
      "url": "",
      "name": "전체 카테고리",
      "path": "홈 화면 상단 검색 영역 아래"
    }
  ],
  "inputs": {
    "sort": {
      "how": "검색 결과 화면에서 '낮은가격순'을 선택합니다. 적용 후 sort=priceASC가 주소에 추가됩니다.",
      "param": "sort"
    },
    "query": {
      "how": "검색 결과 주소의 query 파라미터에 검색어를 넣어 이동합니다.",
      "param": "query"
    }
  },
  "stop_point": "상품 상세의 가격비교 화면(판매처별 '구매하기' 링크가 보이는 곳)에서 멈춥니다. '구매하기'·'최저가 구매하기'는 누르지 않습니다."
}
```

검색 결과 첫 부분의 '이런 상품 어때요? 광고'는 일반 가격비교 결과와 구분해야 합니다.
홈 검색창에서 검색 버튼을 눌렀을 때 주소는 www.danawa.com의 k1 파라미터 형태로 바뀌었으나 검색 결과 화면으로 이동하지 않았으므로, 검색에는 search.danawa.com의 query 주소를 사용하세요.
상품 상세의 '최저가'는 상품가 기준이며, 판매처별 실제 부담액 비교에는 각 행의 '(배송비 …원)'을 더해야 합니다.
'멤버십/카드결제 최대 혜택가'는 조건부 가격으로 일반 최저가와 구분됩니다.
