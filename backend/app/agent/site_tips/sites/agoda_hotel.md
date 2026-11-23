---
name: 아고다 · 호텔
domains: agoda.com
vertical: hotel
aliases: 아고다, agoda
verified: 2026-11-20
---
```spec
{
  "flow": [
    {
      "how": "홈의 숙소 검색 폼에서 지역 자동완성 선택, 체크인·체크아웃 달력 선택, 투숙객·객실 카운터 설정 후 '검색하기'를 누른다. 제주·2026-12-04~2026-12-05·성인 2명·객실 1개로 검색했을 때 검색 결과 화면 상단에 해당 조건이 표시됐고 '검색 결과 0건'이 표시됐다.",
      "key": "search",
      "url": "https://www.agoda.com/ko-kr/search?city={region}&checkIn={checkin}&checkOut={checkout}&los=1&rooms={rooms}&adults={adults}&children=0&locale=ko-kr&currency=KRW&textToSearch={region}"
    },
    {
      "how": "검색 결과 화면에서 정렬 메뉴를 열어 '낮은 요금 순'을 선택했다. URL의 sort 값이 agodaRecommended에서 priceLowToHigh로 변경됐다.",
      "key": "filter",
      "url": "https://www.agoda.com/ko-kr/search?city={region}&checkIn={checkin}&checkOut={checkout}&los=1&rooms={rooms}&adults={adults}&children=0&locale=ko-kr&currency=KRW&textToSearch={region}&sort=priceLowToHigh"
    },
    {
      "how": "목록 카드의 이름·가격은 이 앱 브라우저에서 안정적으로 읽히지 않는다 (목록 상단에 '검색 결과 0건'이 표시되고 카드가 늦게 또는 부분적으로만 나타난다). 목록에서 가격을 비교하려 하지 말고, 보이는 숙소 이름 링크를 눌러 숙소 상세로 들어가 객실 요금(1박당 총 금액·세금 포함·취소 규정)을 읽어 비교한다. 여러 숙소를 비교하려면 숙소마다 상세에 들어갔다가 뒤로 가서 다음 숙소를 연다.",
      "key": "compare",
      "url": "",
      "skip": true
    },
    {
      "how": "숙소 상세에서 상단 '객실' 탭(또는 '객실 상품 보기')을 누르면 객실 행 목록이 나온다. 행마다 '최대 성인 N명', '1박당 총 금액 ₩…', '예약 무료 취소' 또는 '환불 불가' 배지, '취소 정책' 버튼, '예약하기'가 있다(예약하기는 누르지 않는다). 입력 인원(성인 2명)보다 '최대 성인 N명'이 크거나 같은 행을 읽는다. '객실 최대 인원이 초과되었습니다'는 그 행에만 붙는 안내이므로 그 행만 건너뛰고 숙소 전체를 버리지 않는다(다른 행에 맞는 객실이 있다). 취소 규정의 요약은 행의 '예약 무료 취소'·'환불 불가' 배지로 읽고, 자세한 안내는 같은 행의 '취소 정책' 버튼을 눌러 나오는 안내에서 읽는다. '취소 정책' 버튼은 행마다 하나라 같은 이름이 여럿(1/4, 2/4 …)이니 읽으려는 행 바로 뒤의 버튼을 순번으로 고른다.",
      "key": "room",
      "url": "https://www.agoda.com/ko-kr/jeju-halla/hotel/jeju-kr.html?adults={adults}&children=0&rooms={rooms}&checkIn={checkin}&los=1&currencyCode=KRW"
    }
  ],
  "entry": [
    {
      "url": "https://www.agoda.com/ko-kr/search?city={region}&checkIn={checkin}&checkOut={checkout}&los=1&rooms={rooms}&adults={adults}&children=0&locale=ko-kr&currency=KRW&textToSearch={region}&sort=priceLowToHigh",
      "label": "검색 결과"
    }
  ],
  "menus": [
    {
      "url": "https://www.agoda.com/ko-kr/",
      "name": "숙소",
      "path": "홈 화면 상단 카테고리 메뉴 > 숙소"
    }
  ],
  "inputs": {
    "rooms": {
      "how": "검색 폼의 '성인 n명 객실 n개' 버튼을 눌러 투숙객·객실 카운터에서 객실 수를 설정한다. 검색 결과 URL에는 rooms=1로 반영됐다.",
      "param": "rooms"
    },
    "adults": {
      "how": "검색 폼의 '성인 n명 객실 n개' 버튼을 눌러 투숙객·객실 카운터에서 성인 수를 설정한다. 검색 결과 URL에는 adults=2로 반영됐다.",
      "param": "adults"
    },
    "filter": {
      "how": "검색 결과 화면의 정렬 메뉴에서 '낮은 요금 순'을 선택하면 URL의 sort=priceLowToHigh로 변경된다. 왼쪽 '조건 검색'에는 숙소 유형, 1박당 요금 범위, 반려동물 동반 가능 등의 필터가 표시됐다.",
      "param": "sort"
    },
    "region": {
      "how": "홈 또는 검색 결과 상단의 '어디로 떠나시나요?' 검색 입력창을 누르고 지역명을 입력한 뒤 자동완성 목록에서 '제주, 대한민국'을 선택한다. 검색 결과 URL에는 제주 도시 ID가 city=16901로 들어가고, 표시 검색어는 textToSearch=제주로 들어갔다.",
      "param": "city,textToSearch"
    },
    "checkin": {
      "how": "검색 폼의 체크인 날짜 버튼을 누르면 달력이 열리며, 날짜를 선택한다. 검색 결과 URL의 형식은 checkIn=YYYY-MM-DD이다.",
      "param": "checkIn"
    },
    "checkout": {
      "how": "체크인 날짜 선택 뒤 달력에서 체크아웃 날짜를 선택한다. 검색 결과 URL의 형식은 checkOut=YYYY-MM-DD이며, 1박 검색에서는 los=1도 함께 들어갔다.",
      "param": "checkOut"
    },
    "children": {
      "how": "투숙객·객실 카운터에서 아동 수를 설정한다. 아동 0명 검색에서는 children=0으로 반영됐다.",
      "param": "children"
    }
  },
  "stop_point": "객실 요금 줄의 '예약하기' 버튼 앞에서 멈춥니다. 객실 유형별 요금·취소 규정까지 확인한 화면이 끝입니다."
}
```

검색 결과 주소는 추적 파라미터가 많지만 city·checkIn·checkOut·los·rooms·adults·children·locale·currency·textToSearch·sort 만 남긴 짧은 주소로 직접 열어도 조건과 정렬이 그대로 반영된다.
검색 결과 화면 상단에 '검색 결과 0건'이라고 표시돼도 아래 목록에는 숙소 카드가 나온다 (건수 표시가 늦게 갱신되는 것으로 보인다). 건수 표시만 보고 결과가 없다고 판단하지 말고 목록을 읽는다.
숙소 상세의 객실 카드에는 시작가, '1박당 총 금액', '세금 및 수수료 포함 요금', 취소 규정이 표시된다. 예약 진행 버튼은 객실 카드의 '예약하기'이며 누르지 않는다.
검색 결과 주소에서 날짜를 바꿔 다시 열면 숙소 상세의 조회일이 그 날짜로 따라온다. 상세 상단의 조회일이 요청한 날짜와 같은지 확인한다.
목록은 한 화면에 숙소 카드가 2~3개만 보이므로 스크롤하며 읽는다. 첫 카드들은 '아고다 광고 숙소'일 수 있고, 판매 완료이거나 요금이 표시되지 않는 숙소도 섞여 있어 위쪽이 항상 가장 싼 것은 아니다.
목록에서의 가격 비교는 하지 않는다 (설명서의 '숙소 후보 비교' 단계 참고). 숙소 상세의 객실 요금을 기준으로 비교한다.
객실 요금·취소 규정은 숙소 상세의 '객실' 탭 아래 행에서 읽는다(맞는 행이 하나라도 있으면 충분하다). 목록 화면의 '검색 결과 0건'은 무시하고, 숙소 상세에 들어갔다가 목록으로 돌아가면 정렬이 풀릴 수 있으니 목록은 정렬 주소(sort=priceLowToHigh)로 다시 연다.
[확인 방법] 정렬 선택 상태는 화면에 표시되지 않는다: 정렬 주소(sort=priceLowToHigh)로 열었으면 낮은 요금 순이 적용된 것이고 주소의 sort 값으로 확인한다. 목록에서 숙소 가격을 비교하는 단계는 건너뛴다(이 사이트에서는 하지 않는 단계). 한 숙소의 객실 행에서 맞는 객실의 요금·취소 정보를 읽으면 비교 단계의 목적은 충족한다.
