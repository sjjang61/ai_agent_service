---
name: Google Flights
domains: google.com
vertical: flight
aliases: 구글 항공권, 구글플라이트, google flights
skills: flight-ticket-search
verified: 2026-11-23
---
```spec
{
  "flow": [
    {
      "how": "편도 유형, 출발지, 목적지, 출발일을 설정한 뒤 '검색' 버튼을 누른다. 결과는 `/travel/flights/search` 경로에서 표시되고, 조건은 `tfs` 직렬화 파라미터에 담긴다.",
      "key": "search",
      "url": "https://www.google.com/travel/flights/search"
    },
    {
      "how": "결과 화면 상단에서 '필터', '모든 필터', 경유, 항공사, 수하물, 가격, 시간대, 탄소 배출량, 경유 공항, 이동 시간 버튼을 사용한다. 결과 영역에는 '추천', '최저가' 탭과 '인기 항공편순으로 정렬됨' 버튼이 표시된다.",
      "key": "sort",
      "url": ""
    },
    {
      "how": "결과 카드에서 항공사, 출발·도착 시각, 소요 시간, 구간(ICN–NRT), 직항 여부, 탄소 배출량, 가격을 읽는다. 화면에는 가격이 성인 1명의 필수 세금 및 수수료를 포함하며 선택 요금 및 수하물 요금은 별도일 수 있다고 표시된다.",
      "key": "compare",
      "url": "https://www.google.com/travel/flights/search"
    }
  ],
  "entry": [
    {
      "url": "https://www.google.com/travel/flights",
      "label": "Google Flights"
    },
    {
      "url": "https://www.google.com/travel/flights/search",
      "label": "항공편 검색 결과"
    }
  ],
  "menus": [
    {
      "url": "https://www.google.com/travel/flights",
      "name": "항공편",
      "path": "상단 탐색 > 항공편"
    }
  ],
  "inputs": {
    "adults": {
      "how": "상단 인원 버튼('1')을 열어 '성인 추가' 또는 '성인 삭제' 버튼으로 인원을 조절하고 '확인'을 누른다.",
      "param": "tfs"
    },
    "origin": {
      "how": "출발지 입력창에 공항 코드 `ICN`을 입력하고 자동완성 목록의 '인천국제공항 ICN'을 선택한다. 선택 후 URL의 `tfs` 값에 공항 코드가 직렬화되어 반영된다.",
      "param": "tfs"
    },
    "trip_type": {
      "how": "검색 폼 상단의 '왕복' 콤보박스를 열고 '편도'를 선택한다. 선택 후 URL의 `tfs` 값이 변경된다.",
      "param": "tfs"
    },
    "depart_date": {
      "how": "출발일 입력창을 열고 월별 달력에서 요소의 `date=2026-12-04` 값을 가진 날짜를 선택한 뒤 '확인'을 누른다. URL의 `tfs` 직렬화 값에는 날짜가 `2026-12-04` 형식으로 포함된다.",
      "param": "tfs"
    },
    "destination": {
      "how": "목적지 입력창에 공항 코드 `NRT`를 입력하고 자동완성 목록의 '나리타 국제 공항 NRT'를 선택한다. 선택 후 URL의 `tfs` 값에 공항 코드가 직렬화되어 반영된다.",
      "param": "tfs"
    }
  },
  "stop_point": ""
}
```

`tfs`는 편도/왕복, 공항 코드, 날짜, 인원 등을 하나의 불투명한 직렬화 값으로 담으므로 개별 조건을 사람이 읽는 URL 파라미터로 축약할 수 없다.
`/travel/flights/search`에 현재 화면에서 얻은 `tfs`를 포함한 URL로 직접 이동하면 검색 결과가 표시됐다.
달력 날짜는 숫자 라벨이 중복되므로 달력 요소의 `date=YYYY-MM-DD` 값을 기준으로 선택한다.
'최저가' 탭을 누른 뒤 결과 오류가 발생한 사례가 있어, 적용 여부는 결과 카드가 다시 표시되는지 확인해야 한다.
달력의 날짜 칸은 이름이 숫자뿐이고 여러 달이 한 화면에 있다: 요소 목록의 date=YYYY-MM-DD 값으로 원하는 날짜를 고른 뒤 '확인'을 누르고 '검색'을 누른다.
검색 직후 '반환된 결과가 없습니다. 오류가 발생했습니다.'가 한 번 뜨는 경우가 있다: '새로고침' 버튼을 누르면 결과가 나온다. '최저가'·'추천' 같은 정렬 탭을 누르면 '결과를 불러오는 중(N%)'이 잠시 표시되니, 3~5초 기다린 뒤 화면을 다시 읽어 항공편 카드(항공사·시각·소요 시간·경유·가격)를 읽는다.
