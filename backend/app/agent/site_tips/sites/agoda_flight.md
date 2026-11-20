---
name: 아고다 · 항공권
domains: agoda.com
vertical: flight
aliases: 아고다, agoda
verified: 2026-11-20
---
```spec
{
  "flow": [
    {
      "how": "홈 검색 폼에서 편도를 선택하고 출발지·도착지를 자동완성 목록에서 선택한 뒤, 가는 날 달력과 탑승객·좌석 등급 팝업을 설정하고 '항공권 검색하기'를 누른다. 확인된 편도 ICN→NRT, 2026-12-04, 성인 1명, 이코노미 결과 URL은 https://www.agoda.com/ko-kr/flights/results?searchType=1&cabinType=Economy&adults=1&departureFrom=ICN&departureFromType=1&departDate=2026-12-04&arrivalTo=NRT&arrivalToType=1&sort=8 이다.",
      "key": "search",
      "url": "https://www.agoda.com/ko-kr/flights/results?searchType={trip_type}&cabinType={cabin}&adults={adults}&departureFrom={origin}&departureFromType=1&departDate={depart_date}&arrivalTo={destination}&arrivalToType=1&sort=8"
    },
    {
      "how": "검색 결과 상단의 '낮은 요금순', '종합 베스트순', '최단 소요 시간순' 버튼을 누른다. 확인된 URL sort 값은 낮은 요금순=1, 종합 베스트순=8, 최단 소요 시간순=6이다. 왼쪽 패널에서 직항, 위탁 수하물, 항공사, 시간대, 경유 횟수, 1인당 요금, 소요 시간, 출발·도착 공항, 좌석 등급을 필터링할 수 있다.",
      "key": "sort",
      "url": "https://www.agoda.com/ko-kr/flights/results?searchType={trip_type}&cabinType={cabin}&adults={adults}&departureFrom={origin}&departureFromType=1&departDate={depart_date}&arrivalTo={destination}&arrivalToType=1&sort=1"
    },
    {
      "how": "결과 카드에서 항공사, 휴대/위탁 수하물 표기, 출발·도착 시각 및 터미널, 소요 시간, 도착일 변경(+1), 경유 표기, 할인 전후 요금을 읽어 비교한다. 각 카드의 '항공편 정보 펼쳐보기' 버튼으로 세부 정보를 펼칠 수 있다. 화면은 요금을 '탑승객 1인당 평균 요금'으로 표시하고 세금 및 제반요금이 포함된다고 안내한다.",
      "key": "compare",
      "url": ""
    }
  ],
  "entry": [
    {
      "url": "https://www.agoda.com/ko-kr/flights/results?searchType={trip_type}&cabinType={cabin}&adults={adults}&departureFrom={origin}&departureFromType=1&departDate={depart_date}&arrivalTo={destination}&arrivalToType=1&sort=8",
      "label": "항공권 검색 결과"
    }
  ],
  "menus": [
    {
      "url": "https://www.agoda.com/ko-kr/flights",
      "name": "항공",
      "path": "상단 서비스 카테고리 > 항공"
    }
  ],
  "inputs": {
    "cabin": {
      "how": "'1 명 / 이코노미' 버튼을 누르면 탑승객·좌석 등급 팝업이 열리며, 이코노미·프리미엄 이코노미·비즈니스·퍼스트 중 선택한다. URL 값은 Economy였다.",
      "param": "cabinType"
    },
    "adults": {
      "how": "'1 명 / 이코노미' 버튼을 누르면 탑승객·좌석 등급 팝업이 열리며, '성인(12세 이상)' 인원 수를 선택한다. 검색 결과 URL에서는 숫자로 들어간다.",
      "param": "adults"
    },
    "origin": {
      "how": "'출발지' 자동완성 입력창에 공항 코드 또는 도시명을 입력하고, 목록에서 공항을 선택한다. ICN 입력 뒤 '인천 국제공항 ICN'을 선택했다. URL 값은 3자리 공항 코드이며 departureFromType=1이 함께 포함되었다.",
      "param": "departureFrom"
    },
    "trip_type": {
      "how": "항공권 홈 검색 폼 상단의 '편도' 또는 '왕복' 탭을 누른다. 편도 검색 결과 URL에는 searchType=1이 포함되었다.",
      "param": "searchType"
    },
    "depart_date": {
      "how": "'가는 날' 버튼을 눌러 월별 달력에서 날짜를 선택한다. 검색 결과 URL에는 YYYY-MM-DD 형식으로 들어간다.",
      "param": "departDate"
    },
    "destination": {
      "how": "'도착지' 자동완성 입력창에 공항 코드 또는 도시명을 입력하고, 목록에서 공항을 선택한다. NRT 입력 뒤 '나리타 국제공항 NRT'를 선택했다. URL 값은 3자리 공항 코드이며 arrivalToType=1이 함께 포함되었다.",
      "param": "arrivalTo"
    }
  },
  "stop_point": "항공편 카드의 '선택' 버튼을 누르기 전, 검색 결과 목록 화면에서 멈춥니다. 항공편 선택·예약처·승객 정보 화면으로는 가지 않습니다."
}
```

검색 결과는 처음에 “베스트 요금 확보 중...”을 표시했으며 약 3초 후 항공편 카드와 필터가 표시되었다.
검색 URL에서 departureFromType=1 또는 arrivalToType=1을 빼면 출발·도착 조건이 사라져 결과가 비어 있었다.
NRT 로 검색해도 결과에 HND 도착·GMP 출발 항공편이 함께 표시될 수 있다 ('나리타 국제공항 도착편만' 필터는 기본으로 꺼져 있다). 공항을 지정해야 하는 요청이면 항공편마다 출발·도착 공항을 확인할 것.
