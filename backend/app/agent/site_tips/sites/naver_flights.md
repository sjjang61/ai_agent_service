---
name: 네이버 항공권
domains: flight.naver.com
vertical: flight
aliases: 네이버 항공권, 네이버항공권, 네이버 항공
verified: 2026-11-20
---
```spec
{
  "flow": [
    {
      "how": "홈에서 편도 탭, 출발·도착 공항 자동완성 선택, 캘린더 날짜, 인원/좌석 팝업을 설정한 뒤 '검색'을 누른다. 국제선 편도 결과는 공항 코드와 YYYYMMDD 날짜를 URL 경로에 넣고 성인 수와 일반석을 쿼리로 표시했다.",
      "key": "search",
      "url": "https://flight.naver.com/flights/international/{origin}:airport-{destination}:airport-{depart_date}?adult={adults}&fareType=Y"
    },
    {
      "how": "검색 결과 본문의 '가격 낮은 순' 버튼으로 가격순을 확인한다. 같은 화면에 '시각/가격' 필터 버튼이 있어 시간 조건과 가격 조건을 설정할 수 있다. 출발 빠른 순은 주소 끝에 sort=depTime:asc 를 붙인 것으로 확인했다.",
      "key": "sort",
      "url": ""
    },
    {
      "how": "결과는 상단 '인기 항공편'과 아래 '편도 항공편 선택'으로 구성된다. 각 항목에서 항공사, 출발·도착 시각, 직항/경유, 소요 시간, CO2 정보, 결제 조건 및 편도 가격을 확인한다. 예: 집에어 15:00 ICN~17:25 NRT, 직항 02시간 25분, 성인/모든 결제수단, 편도 166,522원~.",
      "key": "compare",
      "url": ""
    }
  ],
  "entry": [
    {
      "url": "https://flight.naver.com/",
      "label": "항공권 홈"
    },
    {
      "url": "https://flight.naver.com/flights/international/{origin}:airport-{destination}:airport-{depart_date}?adult={adults}&fareType=Y",
      "label": "국제선 편도 검색 결과"
    }
  ],
  "menus": [
    {
      "url": "https://flight.naver.com/",
      "name": "항공",
      "path": "상단 여행 서비스 메뉴 > 항공"
    }
  ],
  "inputs": {
    "cabin": {
      "how": "'성인 N명' 버튼의 인원 및 좌석 선택 팝업에서 '일반석·프리미엄·비즈니스' 중 좌석 등급을 고르고 '적용'을 누른다. 일반석 검색 결과에서 fareType=Y가 확인되었다.",
      "param": "fareType"
    },
    "adults": {
      "how": "'성인 N명' 버튼을 눌러 인원 및 좌석 선택 팝업을 열고 성인 증감 버튼으로 1명을 설정한 뒤 '적용'을 누른다.",
      "param": "adult"
    },
    "origin": {
      "how": "출발지 버튼을 누른 뒤 검색 입력창에 공항 코드(ICN)를 입력하고 자동완성 목록의 '인천국제공항 ICN'을 선택한다.",
      "param": "path ({origin}:airport)"
    },
    "trip_type": {
      "how": "홈 검색 폼 상단의 '왕복·편도·다구간' 탭에서 '편도'를 누른다. 편도 결과 URL은 귀국일 경로 구간이 없다.",
      "param": ""
    },
    "depart_date": {
      "how": "날짜 버튼을 눌러 캘린더를 열고 가는 날을 선택한다. 이번에는 2주 뒤 금요일이 2026-12-04로 표시되어 해당 날짜를 선택했다.",
      "param": "path (YYYYMMDD)"
    },
    "destination": {
      "how": "도착지 버튼을 누른 뒤 검색 입력창에 공항 코드(NRT)를 입력하고 자동완성 목록의 '나리타국제공항 NRT'를 선택한다.",
      "param": "path ({destination}:airport)"
    }
  },
  "stop_point": "항공편 카드의 '선택' 버튼을 누르기 전, 검색 결과 목록 화면에서 멈춥니다. 항공편 선택·예약처 선택·승객 정보 화면으로는 가지 않습니다."
}
```

검색 완료 후 결과 로딩은 약 3초 내에 끝났고, 처음에는 ‘로딩 중’이 표시될 수 있다.
결과 상단의 ‘인기 항공편’은 가격순 목록과 별도이며, 실제 가격 비교는 아래 ‘편도 항공편 선택’ 목록에서 한다.
카드 할인 가격에는 ‘성인/특정 카드(이용실적 충족시)’ 조건이 붙을 수 있으므로 ‘성인/모든 결제수단’ 가격과 구분해야 한다.
