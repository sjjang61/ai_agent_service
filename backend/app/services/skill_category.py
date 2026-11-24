"""스킬 설명(description)을 읽어 카테고리로 자동 분류한다.

1) 키워드 규칙으로 점수를 매긴다 (빠르고 비용이 없다). 이름에 든 키워드는 가중치를 더 준다.
2) 한 카테고리가 뚜렷하지 않으면 LLM 에게 고정된 카테고리 목록 중 하나를 고르게 한다 (프롬프트: prompts/skill_category.md).
3) LLM 이 실패하면 규칙 점수가 가장 높은 카테고리, 점수가 없으면 '기타'.
사용자가 직접 고른 카테고리(category_locked)는 건드리지 않는다.
"""
import asyncio
import logging
import re
from typing import Optional

from app.agent.prompts import render

logger = logging.getLogger(__name__)

ETC = "etc"
# (id, 라벨, LLM 에게 주는 설명, 키워드 정규식 조각 — 영어는 단어 앞 경계, 한글은 부분 일치)
CATEGORIES: list[tuple[str, str, str, list[str]]] = [
    ("document", "문서·오피스", "PDF, Word, Excel, PowerPoint 같은 문서·스프레드시트·프레젠테이션 파일을 만들고 읽고 편집",
     [r"pdf", r"docx?\b", r"word\b", r"xlsx?\b", r"excel", r"pptx?\b", r"powerpoint", r"slide", r"spreadsheet", r"document\b", r"presentation",
      r"문서", r"엑셀", r"워드", r"슬라이드", r"발표", r"스프레드시트", r"보고서", r"hwp", r"한글 문서"]),
    ("dev", "개발·코딩", "소프트웨어 개발: 코드 작성·리뷰·디버깅·테스트·배포, 프론트엔드·백엔드, Git",
     [r"code\b", r"coding", r"develop", r"program", r"debug", r"refactor", r"\btest(s|ing)?\b", r"\bgit\b", r"github", r"commit", r"pull request",
      r"frontend", r"backend", r"react", r"typescript", r"javascript", r"python", r"\bapi\b", r"\bsdk\b", r"deploy", r"docker", r"\bci\b", r"playwright", r"web ?app", r"website", r"landing page", r"web page", r"webapp",
      r"개발", r"코드", r"코딩", r"디버그", r"리팩", r"테스트", r"배포", r"프론트", r"백엔드"]),
    ("data", "데이터·분석", "데이터 처리·통계·분석·시각화·SQL·차트·리포트",
     [r"data\b", r"dataset", r"analy[sz]", r"analytics", r"statistic", r"visuali[sz]", r"chart", r"graph\b", r"\bsql\b", r"\bcsv\b", r"pandas", r"dashboard", r"metric", r"forecast",
      r"데이터", r"분석", r"통계", r"시각화", r"차트", r"그래프", r"대시보드", r"지표"]),
    ("design", "디자인·미디어", "UI/UX·그래픽·이미지·영상·오디오·애니메이션·브랜딩 등 디자인과 미디어 제작",
     [r"design", r"\bui\b", r"\bux\b", r"image", r"video", r"audio", r"music", r"canvas", r"figma", r"css\b", r"animation", r"\bgif\b", r"\bart\b", r"brand", r"theme", r"illustrat", r"photo", r"poster", r"font", r"color",
      r"디자인", r"이미지", r"영상", r"동영상", r"음악", r"애니메이션", r"브랜드", r"테마", r"포스터", r"색상"]),
    ("research", "리서치·정보 수집", "웹 검색·크롤링·자료 조사·논문·뉴스·요약 등 정보를 찾고 모으는 일",
     [r"research", r"search", r"crawl", r"scrap", r"browse", r"news", r"paper", r"citation", r"literature", r"investigat", r"fact.?check", r"look.?up", r"fetch", r"weather", r"price", r"results?\b", r"itinerar", r"travel",
      r"리서치", r"검색", r"조사", r"크롤", r"수집", r"뉴스", r"논문", r"자료", r"조회", r"날씨", r"시세", r"가격", r"예보", r"여행"]),
    ("writing", "글쓰기·커뮤니케이션", "글쓰기·편집·번역·이메일·블로그·보고서 초안·공지·사내 커뮤니케이션",
     [r"writ(e|ing|er)\b", r"blog", r"copywrit", r"content\b", r"email", r"\bmail\b", r"translat", r"proofread", r"edit(ing|or)?\b", r"newsletter", r"announcement", r"comms\b", r"communication", r"coauthor", r"co-author", r"essay", r"summar",
      r"글쓰기", r"작성", r"번역", r"이메일", r"메일", r"블로그", r"교정", r"요약", r"공지", r"커뮤니케이션", r"카피"]),
    ("automation", "자동화·연동", "외부 서비스·도구 연동과 반복 작업 자동화: Slack·Notion·캘린더·브라우저 조작·MCP·워크플로",
     [r"automat", r"workflow", r"integrat", r"\bmcp\b", r"slack", r"notion", r"jira", r"calendar", r"scheduler", r"scheduled (task|job)", r"webhook", r"zapier", r"cron", r"bot\b", r"connector", r"browser",
      r"자동화", r"연동", r"워크플로", r"스케줄러", r"예약 작업", r"슬랙", r"노션", r"캘린더", r"봇"]),
    ("business", "업무·비즈니스", "기획·마케팅·영업·재무·인사·회의·프로젝트 관리 같은 업무와 비즈니스",
     [r"business", r"marketing", r"sales", r"finance", r"financ", r"account(ing)?\b", r"\bhr\b", r"recruit", r"meeting", r"project", r"roadmap", r"strategy", r"customer", r"invoice", r"budget", r"\bseo\b", r"proposal", r"\bokr\b",
      r"업무", r"마케팅", r"영업", r"재무", r"회계", r"인사", r"채용", r"회의", r"기획", r"전략", r"고객", r"예산", r"제안서", r"계약"]),
    ("ai", "AI·에이전트", "AI 에이전트·프롬프트·LLM·스킬/플러그인 자체를 만들거나 다루는 일",
     [r"\bai\b", r"\bllm\b", r"prompt", r"agent", r"\bskills?\b", r"claude", r"gpt", r"embedding", r"\brag\b", r"fine.?tun", r"model\b",
      r"에이전트", r"프롬프트", r"스킬", r"인공지능", r"모델"]),
]
CATEGORY_IDS = [c[0] for c in CATEGORIES] + [ETC]
LABELS = {c[0]: c[1] for c in CATEGORIES} | {ETC: "기타"}

_PATTERNS: dict[str, list[re.Pattern]] = {}
for _cid, _label, _desc, _kws in CATEGORIES:
    pats = []
    for kw in _kws:
        # 영어 키워드는 단어 앞 경계를 강제한다 (예: 'doc' 이 'docker' 에 걸리지 않게 키워드 자체를 명시). 한글은 부분 일치.
        pats.append(re.compile((r"(?<![a-z0-9])" + kw) if re.match(r"[a-z\\]", kw) else kw, re.I))
    _PATTERNS[_cid] = pats

# 상세 카테고리: 상위 카테고리 안에서 한 번 더 나눈다. 지금은 '리서치·정보 수집'만 나눈다(18개 이상이 한 묶음에 섞이기 때문).
# (id, 라벨, 키워드) — 위에서부터 점수가 높은 것을 고르고, 동점이면 앞의 것. 아무것도 안 맞으면 SUB_DEFAULT.
SUB_DEFAULT = "general"
SUBCATEGORIES: dict[str, list[tuple[str, str, list[str]]]] = {
    "research": [
        ("shopping", "쇼핑·가격 비교", [r"shop", r"coupang", r"danawa", r"bunjang", r"daangn", r"ohou", r"lowest.?price", r"product", r"deal\b", r"used.?goods", r"marketplace", r"구매", r"쇼핑", r"상품", r"최저가", r"중고", r"쿠팡", r"다나와", r"번개장터", r"당근", r"오늘의집", r"특가", r"배송"]),
        ("transport", "교통·예매 조회", [r"flight", r"airline", r"airport", r"train", r"railway", r"korail", r"\bktx\b", r"\bbus\b", r"kobus", r"timetable", r"subway", r"taxi", r"항공", r"비행기", r"기차", r"철도", r"버스", r"고속버스", r"시간표", r"지하철", r"교통", r"예매"]),
        ("travel", "여행·숙소", [r"travel", r"trip", r"itinerar", r"hotel", r"accommodation", r"airbnb", r"tour", r"destination", r"여행", r"숙소", r"호텔", r"일정", r"관광", r"리조트", r"펜션"]),
        ("realestate", "부동산", [r"real.?estate", r"apartment", r"officetel", r"housing", r"rent\b", r"lease", r"realty", r"부동산", r"아파트", r"전세", r"월세", r"실거래", r"공시가", r"오피스텔", r"청약"]),
        ("finance", "금융·주식", [r"stock", r"securit", r"\bkrx\b", r"\betf\b", r"crypto", r"bitcoin", r"exchange rate", r"\bfund\b", r"interest rate", r"bank", r"loan", r"주식", r"증권", r"종목", r"코스피", r"코스닥", r"환율", r"금융", r"펀드", r"대출", r"금리", r"암호화폐", r"코인"]),
        ("news", "뉴스·시사", [r"news", r"headline", r"breaking", r"press", r"journal", r"current events", r"뉴스", r"헤드라인", r"속보", r"기사", r"시사", r"언론"]),
        ("weather", "날씨·생활 정보", [r"weather", r"forecast", r"air quality", r"dust", r"pollen", r"holiday", r"calendar of", r"날씨", r"기상", r"예보", r"미세먼지", r"황사", r"공휴일", r"생활"]),
        ("sports", "스포츠·공연·행사", [r"sport", r"\bkbo\b", r"baseball", r"soccer", r"football", r"marathon", r"triathlon", r"concert", r"musical", r"exhibition", r"festival", r"schedule", r"야구", r"축구", r"농구", r"배구", r"마라톤", r"경기", r"공연", r"전시", r"축제", r"행사", r"콘서트"]),
        ("academic", "논문·학술 자료", [r"paper", r"arxiv", r"scholar", r"citation", r"literature", r"journal article", r"academic", r"patent", r"thesis", r"논문", r"학술", r"인용", r"특허", r"문헌", r"학위"]),
        (SUB_DEFAULT, "웹 검색·일반 조사", [r"web search", r"crawl", r"scrap", r"browse", r"fact.?check", r"investigat", r"look.?up", r"fetch", r"웹 검색", r"크롤", r"조사", r"자료", r"팩트"]),
    ],
}
SUB_LABELS = {cid: {sid: label for sid, label, _k in subs} for cid, subs in SUBCATEGORIES.items()}
_SUB_PATTERNS: dict[str, list[tuple[str, list[re.Pattern]]]] = {
    cid: [(sid, [re.compile((r"(?<![a-z0-9])" + kw) if re.match(r"[a-z\\]", kw) else kw, re.I) for kw in kws]) for sid, _l, kws in subs]
    for cid, subs in SUBCATEGORIES.items()
}


def subcategory_ids(category: str) -> list[str]:
    return [sid for sid, _l, _k in SUBCATEGORIES.get(category, [])]


def classify_sub(category: str, name: str, description: str) -> Optional[str]:
    """상위 카테고리 안의 상세 카테고리 id. 나누지 않는 카테고리는 None, 맞는 키워드가 없으면 기본(일반)."""
    pats = _SUB_PATTERNS.get(category)
    if not pats:
        return None
    name_l, desc_l = (name or "").replace("-", " ").replace("_", " ").lower(), (description or "").lower()
    best, best_score = SUB_DEFAULT, 0
    for sid, plist in pats:
        if sid == SUB_DEFAULT:
            continue
        s = 0
        for p in plist:
            if p.search(name_l):
                s += 2
            elif p.search(desc_l):
                s += 1
        if s > best_score:  # 동점이면 앞의 것
            best, best_score = sid, s
    return best


CONFIDENT_MIN = 2  # 1위 점수가 이 이상이고, 2위보다 1점 이상 높으면 규칙만으로 확정


def score(name: str, description: str) -> dict[str, int]:
    """카테고리별 키워드 점수. 이름에서 맞은 키워드는 2점, 설명에서만 맞은 키워드는 1점."""
    name_l, desc_l = (name or "").replace("-", " ").replace("_", " ").lower(), (description or "").lower()
    out: dict[str, int] = {}
    for cid, pats in _PATTERNS.items():
        s = 0
        for p in pats:
            if p.search(name_l):
                s += 2
            elif p.search(desc_l):
                s += 1
        if s:
            out[cid] = s
    return out


def classify_by_rules(name: str, description: str) -> tuple[str, bool]:
    """(카테고리 id, 확정 여부). 점수가 없으면 ('etc', False)."""
    s = score(name, description)
    if not s:
        return ETC, False
    ranked = sorted(s.items(), key=lambda kv: (-kv[1], CATEGORY_IDS.index(kv[0])))
    best_id, best = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0
    return best_id, best >= CONFIDENT_MIN and best - second >= 1


def parse_llm_answer(text: str) -> Optional[str]:
    """모델 답변에서 카테고리 id 를 꺼낸다 (따옴표·설명이 섞여도 첫 번째로 나온 유효한 id)."""
    t = (text or "").strip().lower()
    for token in re.findall(r"[a-z]+", t):
        if token in CATEGORY_IDS:
            return token
    return None


async def _ask_llm(name: str, description: str) -> Optional[str]:
    from app.agent.react_agent import AgentRunner
    from app.services.memory_extractor import _content_text

    cats = "\n".join(f"- {cid}: {desc}" for cid, _l, desc, _k in CATEGORIES) + f"\n- {ETC}: 위 어디에도 맞지 않는 경우"
    llm = AgentRunner(tools=[]).llm
    resp = await asyncio.wait_for(
        llm.ainvoke(render("skill_category", categories=cats, name=name, description=(description or "")[:1500])), 30
    )
    return parse_llm_answer(_content_text(resp.content))


async def classify(name: str, description: str, use_llm: bool = True) -> str:
    """스킬 하나의 카테고리 id."""
    best, confident = classify_by_rules(name, description)
    if confident or not use_llm or not (description or "").strip():
        return best
    try:
        answer = await _ask_llm(name, description)
        if answer:
            return answer
    except Exception as e:  # LLM 설정 없음·시간 초과 등: 규칙 결과로 대신한다
        logger.info("skill category LLM fallback (%s): %s", name, type(e).__name__)
    return best


async def classify_many(items: list[tuple[str, str]], use_llm: bool = True, parallel: int = 4) -> list[str]:
    sem = asyncio.Semaphore(parallel)

    async def one(n: str, d: str) -> str:
        async with sem:
            return await classify(n, d, use_llm)

    return list(await asyncio.gather(*(one(n, d) for n, d in items)))
