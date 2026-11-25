---
name: 네이버증권
domains: stock.naver.com
vertical: stock
aliases: 네이버증권, 네이버 증권
verified: 2026-11-25
---
```spec
{
  "flow": [
    {
      "how": "검색창에 종목명을 입력하고 자동완성에서 종목 링크(/domestic/stock/코드/price)를 누른다. 엔터로 제출하지 않는다.",
      "key": "search",
      "url": "https://stock.naver.com/domestic/stock/{stock_code}/price"
    },
    {
      "how": "종목 화면 위쪽의 현재가·전일대비·시세정보(시가·고가·저가·거래량·대금·52주)와 기준 시각을 읽는다.",
      "key": "quote",
      "url": "https://stock.naver.com/domestic/stock/{stock_code}/price"
    },
    {
      "how": "같은 화면의 투자정보(시총·PER·EPS·PBR·BPS·배당수익률)와 컨센서스(투자의견·목표주가·기준일)를 읽는다.",
      "key": "metrics",
      "url": "https://stock.naver.com/domestic/stock/{stock_code}/price"
    },
    {
      "how": "조회한 종목 화면에서 멈춘다. 주문·로그인·관심종목·알림은 누르지 않는다.",
      "key": "stop",
      "url": ""
    }
  ],
  "entry": [
    {
      "url": "https://stock.naver.com/",
      "label": "네이버증권 홈"
    },
    {
      "url": "https://stock.naver.com/domestic/stock/005930/price",
      "label": "종목 화면(예: 삼성전자)"
    }
  ],
  "menus": [
    {
      "url": "https://stock.naver.com/market/stock/kr",
      "name": "국내",
      "path": "상단 메뉴 > 국내"
    },
    {
      "url": "https://stock.naver.com/market/stock/usa",
      "name": "미국·글로벌",
      "path": "상단 메뉴 > 미국 · 글로벌"
    },
    {
      "url": "https://stock.naver.com/market/marketindex",
      "name": "시장지표",
      "path": "상단 메뉴 > 시장지표"
    },
    {
      "url": "https://stock.naver.com/domestic/stock/{stock_code}/info/investment",
      "name": "종목 투자정보",
      "path": "종목 화면 > 투자정보"
    },
    {
      "url": "https://stock.naver.com/domestic/stock/{stock_code}/info/consensus",
      "name": "종목 컨센서스",
      "path": "종목 화면 > 컨센서스"
    }
  ],
  "inputs": {
    "items": {
      "how": "종목 화면 한 곳에 시세정보·투자정보·컨센서스가 모두 텍스트로 나온다. 일별 값은 아래 일별 시세 표, 차트 기간은 조회 기간 버튼으로 바꾼다.",
      "param": ""
    },
    "stock": {
      "how": "상단 검색창(종목명·지수명 입력)에 종목명을 입력하고 자동완성 목록에서 이름·코드·시장이 맞는 항목의 링크를 누른다. 종목코드를 알면 /domestic/stock/{종목코드}/price 로 바로 이동한다.",
      "param": ""
    }
  },
  "stop_point": "종목 화면 — https://stock.naver.com/domestic/stock/005930/price"
}
```

**네이버증권(stock.naver.com)** 이다 (구버전 finance.naver.com 이 아니다).
- 상단 검색창 `종목명·지수명 입력`(input:search, 단축키 ⌘K)에 종목명을 입력하면 자동완성 목록이 열린다. 항목은 `삼성전자 005930 코스피` 처럼 이름·코드·시장으로 표시되고 링크가 `/domestic/stock/{종목코드}/price` 다. 첫 항목이 정확히 일치하는 종목이지만 `RISE 삼성전자SK하이닉스채권혼합50` 같은 ETF 가 뒤따르니 코드로 확인한다. 엔터로 제출하지 말고 목록의 링크를 누른다.
- 종목 화면은 종목코드 주소로 바로 열린다: `https://stock.naver.com/domestic/stock/005930/price`. 해외 종목은 `/worldstock/…` 형태일 수 있으니 검색 결과 링크를 따른다.
- 같은 화면 위쪽에 현재가·전일 대비·정규장 종가·애프터마켓, 시세정보(52주 최저/최고, 기준가, 시가·고가·저가, 거래량·대금), 투자정보(시총, 외인소진율, PER·EPS, 추정PER·EPS, PBR·BPS, 배당수익률·주당배당금, 동일업종 등락률·PER), 컨센서스(투자의견·목표주가와 기준일)가 한 번에 텍스트로 읽힌다. 아래에는 차트와 호가, 일별 시세 표(날짜·종가·전일대비·시가·고가)가 있다.
- 종목 탭 주소: 차트·시세 `/price`, 투자자 동향 `/tradingTrend`, 종목분석 `/info`, 리서치 `/research`, 뉴스·공시 `/news`, 공매도현황 `/shortTrade`, 토론 `/discussion`. 시세정보·투자정보·컨센서스 바로가기는 `/info/company`, `/info/investment`, `/info/consensus`.
- 차트 기간은 '조회 기간'(1일~10년)과 분봉/일/주/월/년 버튼으로 바꾼다. 차트 값은 그림이라 일별 값이 필요하면 아래 일별 시세 표를 읽는다.
- 시세는 `KRX 제공`·`20분지연`, 시/고/저·거래량·52주는 `KRX+NXT 통합 기준`, 시총·투자지표는 `KRX 기준`이라고 화면에 적혀 있다. 보고할 때 이 기준을 함께 적는다.
- 누르지 않는 것: 로그인·MY·관심종목 추가·알림·보유종목, 매수/매도 주문, 토론 글쓰기.
