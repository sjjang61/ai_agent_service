---
name: 네이버 부동산
domains: fin.land.naver.com
vertical: realestate
aliases: 네이버 부동산, 네이버부동산
verified: 2026-11-25
---
```spec
{
  "flow": [
    {
      "how": "검색창에 단지명을 입력해 단지를 고르면 /complexes/단지ID 화면이 열린다. 막히면 단지ID 주소로 바로 이동한다.",
      "key": "search",
      "url": "https://fin.land.naver.com/complexes/{complex_id}"
    },
    {
      "how": "시세 탭을 열어 면적을 고르고 최근 실거래·시세 최고/최저·일반평균가·전세가율·3년 내 최고/최저·실거래 표를 텍스트로 읽는다. 평단가는 총액÷평수로 계산한다.",
      "key": "price",
      "url": "https://fin.land.naver.com/complexes/{complex_id}?tab=transaction"
    },
    {
      "how": "매물 탭을 열어 거래유형(매매)을 고르고 매물 N개와 항목(동·가격·면적·층·방향)을 읽는다. 정렬은 랭킹순·가격순·최신순·면적순.",
      "key": "listings",
      "url": "https://fin.land.naver.com/complexes/{complex_id}?tab=article&articleTradeTypes=A1"
    },
    {
      "how": "매물 목록을 읽은 화면에서 멈춘다. 관심매물·알림·매물 보러가기·중개사 문의는 누르지 않는다.",
      "key": "stop",
      "url": ""
    }
  ],
  "entry": [
    {
      "url": "https://fin.land.naver.com/",
      "label": "신규 네이버 부동산 홈"
    },
    {
      "url": "https://fin.land.naver.com/complexes/919",
      "label": "단지 화면(예: 상계주공5단지)"
    }
  ],
  "menus": [
    {
      "url": "https://fin.land.naver.com/complexes/{complex_id}?tab=transaction",
      "name": "시세",
      "path": "단지 패널 > 시세 탭"
    },
    {
      "url": "https://fin.land.naver.com/complexes/{complex_id}?tab=article",
      "name": "매물",
      "path": "단지 패널 > 매물 탭"
    },
    {
      "url": "https://fin.land.naver.com/complexes/{complex_id}?tab=complex-info",
      "name": "단지정보",
      "path": "단지 패널 > 단지정보 탭"
    }
  ],
  "inputs": {
    "area": {
      "how": "시세 탭은 면적 버튼(예: 37.38㎡ (31.98))으로, 매물 탭은 '전체면적' 버튼으로 평형을 고른다. '면적 단위 변경'으로 ㎡/평을 바꾼다.",
      "param": ""
    },
    "complex": {
      "how": "상단 '단지, 주소, 지하철, 초등학교 검색' 버튼으로 검색창을 열어 단지명을 입력하고 자동완성에서 단지를 고른다. 안 열리면 최근조회·인기 목록의 단지 링크 또는 단지ID 주소(/complexes/숫자)로 이동한다.",
      "param": ""
    },
    "trade_type": {
      "how": "매물 탭 위의 거래유형 버튼(매매·전세·월세)을 고르거나 주소에 articleTradeTypes=A1(매매)/B1(전세)/B2(월세)를 붙인다.",
      "param": "articleTradeTypes"
    }
  },
  "stop_point": "단지 패널의 매물 탭 목록 — https://fin.land.naver.com/complexes/919?tab=article"
}
```

**신규 네이버 부동산(fin.land.naver.com)** 이다. 구버전 new.land.naver.com 은 쓰지 않는다.
- 단지 화면 주소는 `https://fin.land.naver.com/complexes/{단지ID}` (예: 상계주공5단지 = 919). 열면 `/map?layer=…` 주소로 바뀌는데 정상이다. 왼쪽이 단지 패널, 오른쪽이 지도다.
- 탭은 주소로 바로 열 수 있다: 시세 `?tab=transaction`, 매물 `?tab=article` (거래유형 필터 `&articleTradeTypes=A1` 매매 / `B1` 전세 / `B2` 월세), 단지정보 `?tab=complex-info`.
- 단지명 검색: 상단 '단지, 주소, 지하철, 초등학교 검색' 버튼을 누르면 검색창이 열린다. 검색창 입력이 잘 안 되거나 자동완성 선택·최근조회 링크를 눌러도 화면이 바뀌지 않으면(검증 때 실제로 있었다) 단지ID 주소로 바로 이동한다. 단지ID는 검색 결과 링크의 `/complexes/숫자` 에서 읽는다.
- 시세 탭: 면적 버튼(예: `37.38㎡ (31.98)`)으로 평형을 고르고 '면적 단위 변경'으로 ㎡/평을 바꾼다. 화면 텍스트에 '최근 실거래', '시세 최고·최저', '일반평균가(한국부동산원 기준 날짜)', '전세가율', '3년 내 최고·최저', 2026년 계약 실거래 표(계약일·층·가격), '매매/전세 흐름'(매매·전세·갭)이 읽힌다. 기간 탭(1년·3년·5년·7년)으로 범위를 바꾼다. 차트의 값은 평형별 **총액**(예: 6억 6,000)이라서 평단가는 총액 ÷ 평수로 계산해 '계산값'이라고 밝힌다.
- 매물 탭: 목록 위에서 거래유형(매매 등)·전체면적·전체동을 고르고 랭킹순·가격순·최신순·면적순으로 정렬한다. 각 항목에 동, 거래유형, 가격(예: 6억 5,000), 면적(공급㎡·전용), 층/총층, 방향, 확인매물 날짜, 중개사가 나온다. '매물 N개'가 총 건수다. 같은 매물이 여러 중개사로 묶여 'N곳에서 등록했어요 · 펼치기'로 보인다.
- 지도 아래의 '매물·단지·실거래가·평' 스위치는 지도에 표시할 정보를 바꾸는 것이다. 매물 목록은 왼쪽 패널의 '매물' 탭에서 읽는다.
- 지도 위 작은 숫자(`97개의 매물` 등)는 주변 단지 마커이므로 누르면 다른 단지로 넘어간다. 누르지 않는다.
- 누르지 않는 것: '관심매물', '알림', '관심단지', '매물 보러가기'(중개사 사이트로 이동), 중개사 전화·문의, '우리집 인증하기'.
- 로그인된 브라우저에서는 홈의 '최근조회'에 직전 단지가 보인다.
