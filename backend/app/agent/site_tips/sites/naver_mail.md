---
name: 네이버 메일
domains: mail.naver.com
vertical: mail
aliases: 네이버메일, 네이버 메일
verified: 2026-11-20
---
```spec
{
  "flow": [
    {
      "how": "https://mail.naver.com/으로 이동하면 로그인된 상태에서 받은메일함이 열리고 주소는 /v2/folders/0/all 이다.",
      "key": "open",
      "url": "https://mail.naver.com/v2/folders/0/all"
    },
    {
      "how": "상단 ‘상세 검색 열기’에서 검색 조건을 설정한다. 기간은 ‘전체’ 선택기를 열어 ‘1주일’을 선택할 수 있다. 검색어 입력 후 Enter를 누르면 /v2/folders/0/search 경로의 검색 결과로 이동한다. 안 읽은 메일만 찾을 때는 먼저 안읽음 목록(`/v2/folders/0/unread`)으로 들어가 거기서 검색한다 (받은메일함에서 검색하면 안읽음 조건이 빠진다).",
      "key": "search",
      "url": "https://mail.naver.com/v2/folders/0/search?detail=true&body={query}&bodyCond=5&period=1week&exceptTrash=true&type=all"
    },
    {
      "how": "목록에는 메일 상태·보낸 사람·메일 제목·본문 미리보기와 검색 결과에서는 소속 메일함 표시가 보인다. 목록 상단에는 중요 표시·첨부 파일·받는 사람 조건용 필터와 ‘목록/본문 보기’가 있다.",
      "key": "list",
      "url": ""
    },
    {
      "how": "목록 상단 작업 도구모음의 ‘메일 쓰기’, ‘삭제’, ‘이동’, ‘읽음’, ‘스팸신고’, ‘답장’, ‘전체답장’, ‘전달’ 버튼 앞에서 멈춘다.",
      "key": "stop",
      "url": ""
    },
    {
      "how": "목록에서 메일 제목 링크를 누르면 읽기 화면(`/v2/read/0/{메일번호}`)으로 바뀐다. 읽기 화면 위쪽의 '뒤로 가기' 버튼으로 목록에 돌아온다. 열면 읽음으로 바뀐다.",
      "key": "read",
      "url": ""
    }
  ],
  "entry": [
    {
      "url": "https://mail.naver.com/v2/folders/0/all",
      "label": "받은메일함"
    }
  ],
  "menus": [
    {
      "url": "https://mail.naver.com/v2/folders/0/all",
      "name": "받은메일함",
      "path": "왼쪽 메일함 메뉴"
    },
    {
      "url": "",
      "name": "보낸메일함",
      "path": "왼쪽 메일함 메뉴"
    },
    {
      "url": "",
      "name": "스팸메일함",
      "path": "왼쪽 내 메일함 메뉴"
    },
    {
      "url": "",
      "name": "메일 검색",
      "path": "상단 검색 영역"
    }
  ],
  "inputs": {
    "query": {
      "how": "상단의 ‘메일 검색’ 입력창에 검색어를 입력한 뒤 Enter를 누르면 검색 결과 화면으로 이동한다. 상세 검색을 열어 둔 상태에서 검색한 경우 검색어는 내용 조건으로 적용되었다.",
      "param": "body"
    },
    "folder": {
      "how": "왼쪽 메일함 메뉴에서 받은메일함을 누르면 받은메일함 목록으로 이동한다.",
      "param": ""
    },
    "period": {
      "how": "상단 ‘상세 검색 열기’에서 기간 선택을 열고 ‘1주일’을 누른 뒤 검색한다. 검색 결과 주소에는 period=1week 및 검색 시점 기준의 periodStart·periodEnd 날짜가 YYYYMMDD 형식으로 추가되었다.",
      "param": "period"
    },
    "unread_only": {
      "how": "안 읽은 메일만 보려면 안읽음 목록(`/v2/folders/0/unread`)에서 검색하거나 상세 검색을 연다. 안읽음 목록에서 검색하면 주소가 `/v2/folders/0/unread/search?detail=true&body={검색어}&bodyCond=5&...` 로 바뀌고 안읽음 조건이 유지된다. 일반 받은메일함에서 상세 검색하면 `/v2/folders/0/search` 로 바뀌어 안읽음 조건이 빠진다.",
      "param": ""
    }
  },
  "stop_point": "메일 목록 화면의 상단 작업 도구모음(메일 쓰기·삭제·이동·읽음 등)"
}
```

상세 검색에서 ‘1주일’을 적용해 검색하면 주소에 `period=1week` 외에 검색 시점 기준 `periodStart`·`periodEnd`가 함께 붙으므로, 기간 조건은 주소 조합보다 화면의 기간 버튼으로 설정하는 편이 안전하다.
`/v2/folders/0/search` 주소에서 `period=1week`만 남기고 날짜 파라미터를 제거해 직접 열면 화면의 기간 제한 결과가 유지되지 않았다.
안읽음 필터는 받은메일함 목록의 안읽음 메일 목록 링크로 진입했으며 주소 경로는 `/v2/folders/0/unread`였다.
안읽음 목록(`/v2/folders/0/unread`)에서 검색하면 결과 주소가 `/v2/folders/0/unread/search?...` 로 바뀌며 안읽음 조건이 유지된다. 받은메일함에서 검색하면 `/v2/folders/0/search` 로 안읽음 조건이 빠진다.
메일을 열면 주소가 `/v2/read/0/{메일번호}` 형태로 바뀌고, '뒤로 가기' 버튼으로 목록으로 돌아온다.
