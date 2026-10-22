export interface McpPresetEnv {
  key: string
  /** 값 입력칸 아래에 보여 줄 설명 */
  hint: string
  /** true 면 비워 둬도 된다 (비우면 서버에 전달하지 않는다) */
  optional?: boolean
}

/** 자주 쓰는 MCP 서버 템플릿. 선택하면 등록 폼이 채워지고 인증 값만 입력하면 된다. */
export interface McpPreset {
  id: string
  name: string
  display_name: string
  description: string
  command: string
  args: string[]
  env: McpPresetEnv[]
  /** 인증 준비 절차 (순서대로) */
  authSteps: string[]
  docsUrl: string
}

export const MCP_PRESETS: McpPreset[] = [
  {
    id: 'gmail',
    name: 'gmail',
    display_name: 'Gmail',
    description: '메일 검색·읽기·작성·라벨 관리',
    command: 'npx',
    args: ['-y', '@gongrzhe/server-gmail-autoauth-mcp'],
    env: [
      { key: 'GMAIL_OAUTH_PATH', hint: 'OAuth 클라이언트 키 파일(gcp-oauth.keys.json) 경로. 비우면 ~/.gmail-mcp/ 를 사용합니다', optional: true },
      { key: 'GMAIL_CREDENTIALS_PATH', hint: '인증 후 저장되는 토큰 파일(credentials.json) 경로. 비우면 ~/.gmail-mcp/ 를 사용합니다', optional: true },
    ],
    authSteps: [
      'Google Cloud 콘솔에서 Gmail API 를 켜고 “데스크톱 앱” 유형의 OAuth 클라이언트 ID 를 만들어 JSON 을 받습니다.',
      '파일 이름을 gcp-oauth.keys.json 으로 바꿔 서버 PC 의 ~/.gmail-mcp/ 에 둡니다.',
      '서버 PC 터미널에서 npx @gongrzhe/server-gmail-autoauth-mcp auth 를 실행해 브라우저에서 로그인합니다 (최초 1회).',
    ],
    docsUrl: 'https://www.npmjs.com/package/@gongrzhe/server-gmail-autoauth-mcp',
  },
  {
    id: 'google-drive',
    name: 'google-drive',
    display_name: 'Google Drive',
    description: 'Drive 파일 검색과 문서·시트 내용 읽기 (읽기 전용)',
    command: 'npx',
    args: ['-y', '@modelcontextprotocol/server-gdrive'],
    env: [
      { key: 'GDRIVE_OAUTH_PATH', hint: 'OAuth 클라이언트 키 파일(gcp-oauth.keys.json)의 절대 경로' },
      { key: 'GDRIVE_CREDENTIALS_PATH', hint: '인증 후 토큰이 저장될 파일의 절대 경로 (예: /data/mcp/gdrive-credentials.json)' },
    ],
    authSteps: [
      'Google Cloud 콘솔에서 Google Drive API 를 켜고 OAuth 동의 화면에 drive.readonly 범위를 추가합니다.',
      '“데스크톱 앱” 유형의 OAuth 클라이언트 ID 를 만들어 JSON 을 받고, 위 경로에 gcp-oauth.keys.json 으로 둡니다.',
      '서버 PC 터미널에서 두 환경변수를 지정하고 npx -y @modelcontextprotocol/server-gdrive auth 를 실행해 로그인합니다 (최초 1회).',
    ],
    docsUrl: 'https://www.npmjs.com/package/@modelcontextprotocol/server-gdrive',
  },
  {
    id: 'google-search',
    name: 'google-search',
    display_name: 'Google Search',
    description: 'Google Programmable Search 로 웹 검색',
    command: 'npx',
    args: ['-y', '@adenot/mcp-google-search'],
    env: [
      { key: 'GOOGLE_API_KEY', hint: 'Google Cloud 콘솔의 Custom Search API 키' },
      { key: 'GOOGLE_SEARCH_ENGINE_ID', hint: 'Programmable Search Engine 의 검색엔진 ID (cx)' },
    ],
    authSteps: [
      'Google Cloud 콘솔에서 Custom Search API 를 켜고 API 키를 만듭니다.',
      'programmablesearchengine.google.com 에서 검색엔진을 만들고 검색엔진 ID(cx)를 복사합니다.',
      '아래 환경변수에 API 키와 검색엔진 ID 를 입력합니다 (브라우저 로그인은 필요 없습니다).',
    ],
    docsUrl: 'https://www.npmjs.com/package/@adenot/mcp-google-search',
  },
]
