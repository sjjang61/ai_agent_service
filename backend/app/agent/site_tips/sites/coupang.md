---
name: 쿠팡
domains: coupang.com
vertical: shopping
aliases: 쿠팡, coupang
skills: coupang-product-search
verified: 2026-11-24
---
```spec
{
  "flow": [
    {
      "how": "검색 결과 주소로 이동한다. 목록에 상품명, 가격, 배송 안내, 리뷰 수 등 일부 정보가 표시되며 광고 상품은 '광고'로 표시된다.",
      "key": "search",
      "url": "https://www.coupang.com/np/search?q={query}"
    },
    {
      "how": "검색 결과의 정렬에서 '낮은가격순'을 선택한다. 주소에 sorter=salePriceAsc가 추가된다. 정렬은 상품가 기준이며, 배송비는 별도로 표시될 수 있다.",
      "key": "sort",
      "url": "https://www.coupang.com/np/search?q={query}&sorter=salePriceAsc"
    },
    {
      "how": "정렬 결과에서 같은 규격의 상품들을 비교한다. 검색 결과에는 상품명, 가격, 배송비 또는 무료배송 안내, 도착 정보, 리뷰·적립 정보가 표시될 수 있다. 가격·배송 조건은 상품별로 다르며 판매처별 가격을 확인해야 한다. 이번 결과에서 봉지 5개입 후보로 확인된 항목은 '오뚜기 진라면 순한맛 120g, 5개' 3,950원(와우는 무료배송 ∙ 무료반품 ∙ 새벽도착), '진라면순한맛(멀티) 120Gx5입(주)오뚜기, 1팩' 4,570원(배송비 3,500원 조건부 무료배송), '진라면 순한맛 5입 멀티 ace1407hM, 5개' 7,350원(배송비 3,000원)이다. 표시된 판매처명은 확인되지 않았다.",
      "key": "compare",
      "url": "https://www.coupang.com/np/search?q={query}&sorter=salePriceAsc"
    },
    {
      "how": "검색 결과의 상품 항목을 눌러 쿠팡 상품 상세로 이동한다. 확인한 상품 상세에서 상품명·가격·규격·배송 정보와 옵션별 수량 가격이 표시됐다. '모든 옵션 보기' 영역에서 판매처별 정보가 추가되는지 확인할 수 있으나 이번 확인에서는 판매처명을 확인하지 못했다.",
      "key": "detail",
      "url": "https://www.coupang.com/vp/products/5587102353?itemId=18843258628&vendorItemId=3000235955"
    },
    {
      "how": "상품 상세에서 '바로구매'를 누르면 구매 진행으로 이어질 수 있다. 이 버튼은 누르지 않았다.",
      "key": "stop",
      "url": "https://www.coupang.com/vp/products/5587102353?itemId=18843258628&vendorItemId=3000235955"
    }
  ],
  "entry": [
    {
      "url": "https://www.coupang.com/np/search?q={query}&sorter=salePriceAsc",
      "label": "검색 결과"
    }
  ],
  "menus": [
    {
      "url": "",
      "name": "카테고리",
      "path": "상단 메뉴"
    },
    {
      "url": "https://www.coupang.com/np/campaigns/82",
      "name": "로켓배송",
      "path": "상단 메뉴"
    },
    {
      "url": "https://www.coupang.com/np/categories/393760",
      "name": "로켓프레시",
      "path": "상단 메뉴"
    },
    {
      "url": "https://www.coupang.com/np/coupangglobal",
      "name": "로켓직구",
      "path": "상단 메뉴"
    },
    {
      "url": "https://www.coupang.com/",
      "name": "쿠팡 홈",
      "path": "상품 상세 > breadcrumb"
    },
    {
      "url": "https://www.coupang.com/np/categories/194276",
      "name": "식품",
      "path": "검색 결과 > 카테고리"
    }
  ],
  "inputs": {
    "sort": {
      "how": "검색 결과의 정렬 항목에서 '낮은가격순'을 선택하면 주소에 sorter=salePriceAsc가 붙는다. 주소 파라미터로 직접 적용할 수도 있다.",
      "param": "sorter"
    },
    "query": {
      "how": "검색창에 검색어를 입력하고 검색하거나, 검색 결과 주소의 q 파라미터로 전달한다. 공백은 URL에서 + 또는 %20으로 인코딩된다.",
      "param": "q"
    }
  },
  "stop_point": "상품 상세 화면의 '바로구매' 버튼 직전: https://www.coupang.com/vp/products/5587102353?itemId=18843258628&vendorItemId=3000235955"
}
```

- 검색 결과 주소는 `q={query}`를 사용하며, 낮은 가격순은 `sorter=salePriceAsc`로 지정한다.
- 검색 결과의 광고 상품은 상품 목록 중 '광고' 표시로 구분한다.
- 상품 상세에는 '장바구니 담기'와 '바로구매' 버튼이 있다. 상태 변경을 피하기 위해 누르지 않는다.
