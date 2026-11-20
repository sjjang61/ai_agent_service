---
name: 스카이스캐너
domains: skyscanner.co.kr
vertical: flight
aliases: 스카이스캐너, skyscanner
verified: 2026-11-20
---
```spec
{
  "flow": [
    {
      "how": "홈의 항공권 검색 폼에서 여행 유형, 출발지·도착지 자동완성, 달력의 가는 날, 여행자 및 좌석 등급을 설정하고 '검색하기'를 누른다. 이번 조건은 https://www.skyscanner.co.kr/transport/flights/icn/nrt/261204/?adultsv2=1&cabinclass=economy&rtn=0 에서 결과가 표시됐다.",
      "key": "search",
      "url": "https://www.skyscanner.co.kr/transport/flights/{origin}/{destination}/{depart_date}/?adultsv2={adults}&cabinclass={cabin}&rtn=0"
    },
    {
      "how": "결과 목록의 '정렬' 드롭다운에서 추천순, 최저가순, 최단여행시간순, 출국: 출발 시간 중 선택한다. 최저가순을 선택해도 확인한 URL은 바뀌지 않았다. 왼쪽/상단 필터에서 경유, 출발 시간대, 총 소요시간, 경유 공항, 항공사, 탄소배출량을 설정할 수 있다.",
      "key": "sort",
      "url": "https://www.skyscanner.co.kr/transport/flights/{origin}/{destination}/{depart_date}/?adultsv2={adults}&cabinclass={cabin}&rtn=0"
    },
    {
      "how": "각 결과 카드에서 항공사, 출발·도착 공항 및 시각, 소요 시간, 직항/경유, 세금과 수수료 포함 여부, '총 금액', 항공편 옵션 수를 비교한다.",
      "key": "compare",
      "url": "https://www.skyscanner.co.kr/transport/flights/{origin}/{destination}/{depart_date}/?adultsv2={adults}&cabinclass={cabin}&rtn=0"
    }
  ],
  "entry": [
    {
      "url": "https://www.skyscanner.co.kr/transport/flights/{origin}/{destination}/{depart_date}/?adultsv2={adults}&cabinclass={cabin}&rtn=0",
      "label": "항공권 검색 결과"
    }
  ],
  "menus": [
    {
      "url": "https://www.skyscanner.co.kr/flights",
      "name": "항공권",
      "path": "상단 탭"
    }
  ],
  "inputs": {
    "cabin": {
      "how": "'여행자 및 좌석 등급' 팝업의 좌석 등급 드롭다운에서 일반석, 프리미엄 일반석, 비즈니스석, 일등석 중 선택하고 '적용'을 누른다. 일반석은 cabinclass=economy로 확인했다.",
      "param": "cabinclass"
    },
    "adults": {
      "how": "'여행자 및 좌석 등급' 버튼을 눌러 팝업을 열고 성인 인원 수 추가/감소 버튼으로 인원을 설정한 뒤 '적용'을 누른다. 성인 1명은 adultsv2=1로 확인했다.",
      "param": "adultsv2"
    },
    "origin": {
      "how": "출발지 입력창에 공항 코드(ICN)를 입력하고 자동완성 목록의 '인천 국제 (ICN)'를 선택한다. 검색 결과 URL 경로의 첫 번째 공항 코드 세그먼트로 들어간다.",
      "param": ""
    },
    "trip_type": {
      "how": "홈 검색 폼의 '왕복' 버튼을 눌러 여행 유형 선택 팝업을 열고 '편도'를 선택한다. 편도 검색 결과 URL에는 rtn=0이 들어갔다.",
      "param": "rtn"
    },
    "depart_date": {
      "how": "가는 편 날짜 버튼을 눌러 달력을 열고 날짜를 선택한 뒤 '적용'을 누른다. 검색 결과 URL 경로의 날짜 세그먼트에 YYMMDD 형식으로 들어간다.",
      "param": ""
    },
    "destination": {
      "how": "도착지 입력창에 공항 코드(NRT)를 입력하고 자동완성 목록의 '도쿄 나리타 (NRT)'를 선택한다. 검색 결과 URL 경로의 두 번째 공항 코드 세그먼트로 들어간다.",
      "param": ""
    }
  },
  "stop_point": "항공편 카드의 '선택하기' 버튼을 누르기 전, 검색 결과 목록 화면에서 멈춥니다. 항공편 선택·예약처·승객 정보 화면으로는 가지 않습니다."
}
```

검색 결과는 약 3초 후 표시됐다.
결과 URL은 공항 코드와 날짜를 쿼리가 아니라 `/transport/flights/{origin}/{destination}/{depart_date}/` 경로에 넣으며, 날짜는 YYMMDD 형식이다.
정렬은 URL 파라미터가 아니라 결과 화면의 `정렬` 드롭다운으로 적용된다.
검색 결과 카드의 가격은 화면에 `총 금액` 및 `세금과 수수료 포함 가격`으로 표시된다.
결과 주소의 공항 코드는 소문자다 (ICN → `icn`, NRT → `nrt`).
정렬이 적용됐는지는 주소가 아니라 화면의 정렬 선택값과 '최저가 기준으로 정렬한 검색 결과 N개' 문구로 확인한다. 가격은 실시간으로 변동한다.
