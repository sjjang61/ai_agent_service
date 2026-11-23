"""웹사이트 분석의 카테고리(상위 분류). 카테고리 아래에 분야(상세 카테고리), 분야 아래에 사이트가 있다.

    카테고리(교통) > 분야(항공권, 교통 예약) > 사이트(스카이스캐너, 코레일)

분야가 없는 사이트(검색엔진 등)는 카테고리에 바로 속한다. 카테고리는 에이전트에게 주는 지침이 아니라 화면에서 사이트를 묶어 보는 분류다.
"""

# (key, 이름) — 표시 순서. 분야·사이트의 category 는 이 key 중 하나이거나 비어 있다(미분류).
CATEGORIES: list[tuple[str, str]] = [
    ("shopping", "쇼핑"),
    ("transport", "교통"),
    ("travel", "여행·숙박"),
    ("realestate", "부동산"),
    ("finance", "금융"),
    ("culture", "문화·생활"),
    ("communication", "커뮤니케이션"),
    ("search", "검색"),
]
KEYS = tuple(k for k, _ in CATEGORIES)
NAMES = dict(CATEGORIES)


def normalize(raw) -> str:
    """알려진 카테고리 key 면 그대로, 비었으면 '', 모르는 값이면 ValueError."""
    key = (raw or "").strip().lower()
    if key and key not in NAMES:
        raise ValueError(f"알 수 없는 카테고리입니다: {key}")
    return key
