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
**접속 차단(Access Denied) 이면 멈춘다**: 'Access Denied — You don't have permission to access … Reference #…' (errors.edgesuite.net) 화면은 쿠팡의 봇 차단이다. 같은 주소를 다시 열거나, 주소를 바꿔 보거나, 다른 경로·http 로 우회하지 않는다. 한 번 나오면 바로 멈추고 '쿠팡이 자동 접속을 차단해 조회하지 못했다(홈을 사람이 한 번 열어 정상인지 확인 필요)'고 알린다. 다른 사이트의 가격으로 대신 답하지 않는다.
**검색 주소는 항상 https 와 q 값을 채운다**: `https://www.coupang.com/np/search?q=검색어` 형태만 쓴다. `http://` 로 열거나 `q=` 를 비운 채(`/np/search?`) 열지 않는다. 검색어를 모르면 주소를 만들지 말고 홈의 검색창에 입력한다.
**검색은 홈의 검색창으로 시작한다 (사람이 쓰는 순서)**: 먼저 `https://www.coupang.com/` 홈을 열어 화면이 뜨는 것을 확인하고, 상단 검색창에 검색어를 입력해 검색한다. 검색 결과 주소(`/np/search?q=…`)로 바로 들어가는 것은 홈이 정상으로 열린 뒤에 같은 탭에서 정렬(낮은가격순)을 바꿀 때만 쓴다. 홈이 열리지 않거나 Access Denied 가 나오면 위 차단 지침대로 멈춘다.
