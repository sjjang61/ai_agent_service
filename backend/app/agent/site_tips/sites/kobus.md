---
name: 고속버스 통합예매(KOBUS)
domains: kobus.co.kr
vertical: transport
aliases: 고속버스, 코버스, kobus
skills: express-bus-booking
status: draft
verified: 
---
```spec
{
  "flow": [
    {
      "how": "메인 또는 상단 주메뉴의 ‘고속버스 예매’를 눌러 https://www.kobus.co.kr/mrs/rotinf.do 로 이동한다. 출발지·도착지·날짜를 각각 선택한 뒤 조회 버튼을 누르면 배차조회 화면 https://www.kobus.co.kr/mrs/alcnSrch.do 로 이동한다.",
      "key": "search",
      "url": "https://www.kobus.co.kr/mrs/rotinf.do"
    },
    {
      "how": "노선조회 완료 후 배차조회 화면에서 시간표 목록을 확인한다.",
      "key": "list",
      "url": "https://www.kobus.co.kr/mrs/alcnSrch.do"
    }
  ],
  "entry": [
    {
      "url": "https://www.kobus.co.kr/main.do",
      "label": "KOBUS 메인"
    },
    {
      "url": "https://www.kobus.co.kr/mrs/rotinf.do",
      "label": "고속버스 예매(노선조회)"
    }
  ],
  "menus": [
    {
      "url": "https://www.kobus.co.kr/mrs/rotinf.do",
      "name": "고속버스 예매",
      "path": "상단 주메뉴 > 고속버스예매 > 고속버스 예매"
    },
    {
      "url": "",
      "name": "시간표 조회",
      "path": "상단 주메뉴 > 운행정보 > 시간표 조회"
    }
  ],
  "inputs": {
    "to": {
      "how": "고속버스 예매 노선조회 화면에서 도착지를 눌러 터미널 선택 레이어에서 선택한다.",
      "param": ""
    },
    "date": {
      "how": "노선조회 화면의 날짜 선택 버튼을 눌러 달력에서 날짜를 선택한다.",
      "param": ""
    },
    "from": {
      "how": "고속버스 예매 노선조회 화면에서 출발지를 눌러 터미널 선택 레이어에서 선택한다.",
      "param": ""
    }
  },
  "stop_point": ""
}
```

첫 방문 시 ‘고속버스 안내’, ‘고속버스 운행 안내’, ‘와이파이 서비스 안내’ 팝업이 순차적으로 겹쳐 표시된다. 각 팝업의 ‘닫기’를 하나씩 누르고 매번 화면을 다시 읽어 다음 팝업을 닫는다.
메인에서 ‘고속버스 예매’를 누르면 노선조회 화면 https://www.kobus.co.kr/mrs/rotinf.do 로 이동한다.
노선조회 완료 후 배차조회 화면 주소는 https://www.kobus.co.kr/mrs/alcnSrch.do 이다.
출발지·도착지 선택 창은 터미널을 고른 뒤 아래 '선택완료' 버튼을 눌러야 반영된다. '조회하기'를 누르면 응답이 느리거나 멈춘 것처럼 보일 수 있다(로딩 시간 초과가 난 적이 있다). 우회하지 말고 기다린 뒤 화면을 다시 읽고, 계속 안 되면 그 사실을 기록한다.
