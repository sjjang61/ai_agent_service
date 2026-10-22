"""create_widget: 답변 내용을 표·차트·흐름도·지도·핵심 수치 카드·프로세스 다이어그램 위젯으로 만든다.

LLM 이 만든 spec 을 검증·정규화해서 JSON 으로 돌려주고, 프론트엔드가 이 결과(tool_result)를 읽어
채팅 말풍선 안에 위젯으로 렌더링한다. 검증에 실패하면 오류 문장을 반환해 LLM 이 고쳐 다시 호출하게 한다.
"""
import json
import re
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, ValidationError, field_validator

from langchain_core.tools import BaseTool

MAX_CELL = 500
_MERMAID_TYPES = (
    "flowchart", "graph", "sequenceDiagram", "classDiagram", "stateDiagram", "stateDiagram-v2",
    "erDiagram", "gantt", "journey", "pie", "mindmap", "timeline", "gitGraph",
)


def _cell(v: Any) -> Union[str, int, float]:
    if isinstance(v, bool) or v is None:
        return "" if v is None else str(v)
    if isinstance(v, (int, float)):
        return v
    return str(v)[:MAX_CELL]


class TableSpec(BaseModel):
    columns: list[str] = Field(min_length=1, max_length=30)
    rows: list[list[Any]] = Field(max_length=300)
    caption: Optional[str] = Field(default=None, max_length=300)

    @field_validator("rows")
    @classmethod
    def _rows(cls, rows, info):
        n = len(info.data.get("columns", []))
        out = []
        for i, r in enumerate(rows):
            if not isinstance(r, list):
                raise ValueError(f"rows[{i}] 는 배열이어야 합니다")
            if len(r) != n:
                raise ValueError(f"rows[{i}] 의 셀 수({len(r)})가 columns 수({n})와 다릅니다")
            out.append([_cell(c) for c in r])
        return out


class Series(BaseModel):
    name: str = Field(max_length=100)
    values: list[float] = Field(max_length=500)


class ChartSpec(BaseModel):
    chart_type: Literal["bar", "line", "pie"]
    labels: list[str] = Field(min_length=1, max_length=200)
    series: list[Series] = Field(min_length=1, max_length=10)
    unit: Optional[str] = Field(default=None, max_length=20)

    @field_validator("series")
    @classmethod
    def _series(cls, series, info):
        n = len(info.data.get("labels", []))
        for s in series:
            if len(s.values) != n:
                raise ValueError(f"series '{s.name}' 의 values 수({len(s.values)})가 labels 수({n})와 다릅니다")
        return series


class FlowSpec(BaseModel):
    mermaid: str = Field(min_length=5, max_length=6000)

    @field_validator("mermaid")
    @classmethod
    def _mermaid(cls, v):
        v = v.strip()
        if not v.startswith(_MERMAID_TYPES):
            raise ValueError("mermaid 는 flowchart/graph/sequenceDiagram 등 다이어그램 종류로 시작해야 합니다")
        if re.search(r"<\s*script|javascript:|^\s*click\s", v, re.IGNORECASE | re.MULTILINE):
            raise ValueError("허용되지 않는 구문(script/javascript:/click)이 포함되어 있습니다")
        return v


class Marker(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    label: str = Field(max_length=100)
    description: Optional[str] = Field(default=None, max_length=300)


class MapSpec(BaseModel):
    markers: list[Marker] = Field(min_length=1, max_length=100)
    center: Optional[tuple[float, float]] = None
    zoom: Optional[int] = Field(default=None, ge=1, le=18)


class StatItem(BaseModel):
    label: str = Field(max_length=60)
    value: str = Field(max_length=30)  # "44개", "약 100배", "1/100" 처럼 단위가 붙은 표시용 문자열
    note: Optional[str] = Field(default=None, max_length=100)
    tone: Literal["default", "positive", "negative", "accent"] = "default"

    @field_validator("value", mode="before")
    @classmethod
    def _value(cls, v):
        return str(v)


class StatsSpec(BaseModel):
    items: list[StatItem] = Field(min_length=1, max_length=12)
    columns: Optional[int] = Field(default=None, ge=1, le=4)  # 한 줄에 놓을 카드 수 (생략하면 자동)
    caption: Optional[str] = Field(default=None, max_length=300)


ProcessIcon = Literal[
    "bot", "user", "users", "file", "check", "search", "database", "chart", "mail", "code",
    "clock", "settings", "globe", "shield", "star", "none",
]


class ProcessItem(BaseModel):
    title: str = Field(max_length=60)
    description: Optional[str] = Field(default=None, max_length=120)
    icon: ProcessIcon = "none"
    highlight: bool = False  # 강조 배경 (예: 평가 대상인 쪽)


class ProcessStage(BaseModel):
    items: list[ProcessItem] = Field(min_length=1, max_length=4)  # 2개 이상이면 나란히(병렬) 배치
    kind: Literal["step", "result"] = "step"  # result: 테두리 상자로 표시 (최종 결과/판정)


class ProcessSpec(BaseModel):
    stages: list[ProcessStage] = Field(min_length=2, max_length=8)  # 위에서 아래로 화살표로 이어진다
    caption: Optional[str] = Field(default=None, max_length=300)


_SPECS = {
    "table": TableSpec, "chart": ChartSpec, "flow": FlowSpec, "map": MapSpec,
    "stats": StatsSpec, "process": ProcessSpec,
}


class CreateWidgetInput(BaseModel):
    widget_type: Literal["table", "chart", "flow", "map", "stats", "process"] = Field(
        description=(
            "Kind of widget: table (comparison table), chart (bar/line/pie), flow (Mermaid diagram), map (markers), "
            "stats (key-number cards), process (simple step-by-step diagram, optionally with parallel branches)"
        )
    )
    title: str = Field(description="Short widget title shown above it")
    spec: dict = Field(
        description=(
            "Widget data. By widget_type: "
            "table -> {\"columns\": [\"항목\",\"A\",\"B\"], \"rows\": [[\"가격\",\"1\",\"2\"]], \"caption\": optional}; "
            "chart -> {\"chart_type\": \"bar\"|\"line\"|\"pie\", \"labels\": [\"1월\",\"2월\"], "
            "\"series\": [{\"name\": \"매출\", \"values\": [10, 20]}], \"unit\": optional}; "
            "flow -> {\"mermaid\": \"flowchart TD\\n  A[시작] --> B{조건}\\n  B -->|예| C[처리]\"} (Mermaid syntax); "
            "map -> {\"markers\": [{\"lat\": 37.5665, \"lon\": 126.978, \"label\": \"서울시청\", \"description\": optional}], "
            "\"center\": [lat, lon] optional, \"zoom\": 1-18 optional}; "
            "stats -> {\"items\": [{\"label\": \"평가 대상 직업\", \"value\": \"44개\", \"note\": \"9개 주요 산업 분야\", "
            "\"tone\": \"default\"|\"positive\"|\"negative\"|\"accent\"}], \"columns\": 1-4 optional}; "
            "process -> {\"stages\": [{\"items\": [{\"title\": \"AI 모델\", \"description\": \"결과물 생성\", "
            "\"icon\": \"bot\", \"highlight\": false}, {\"title\": \"인간 전문가\", \"icon\": \"user\"}], "
            "\"kind\": \"step\"|\"result\"}]} (stages are drawn top to bottom joined by arrows; items inside one stage sit side by side)"
        )
    )


class CreateWidgetTool(BaseTool):
    name: str = "create_widget"
    description: str = (
        "Turn part of the answer into a visual widget shown in the chat: a comparison table, a bar/line/pie chart, "
        "a flowchart/diagram (Mermaid), a map with markers, key-number cards (stats) or a simple step diagram "
        "(process). Use it when content is easier to grasp visually (comparisons, trends, processes, locations, "
        "headline numbers). The widget is displayed to the user automatically; "
        "do not repeat its full data in the text, just summarize the key point."
    )
    args_schema: type[BaseModel] = CreateWidgetInput

    def _run(self, widget_type: str, title: str, spec: dict) -> str:
        try:
            model = _SPECS[widget_type].model_validate(spec)
        except ValidationError as e:
            problems = "; ".join(
                f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()[:5]
            )
            return f"Error: invalid {widget_type} spec - {problems}. Fix the spec and call create_widget again."
        except KeyError:
            return f"Error: unknown widget_type '{widget_type}'"
        widget = {"type": widget_type, "title": title.strip()[:200], "spec": model.model_dump(exclude_none=True)}
        return json.dumps({"ok": True, "widget": widget}, ensure_ascii=False)

    async def _arun(self, widget_type: str, title: str, spec: dict) -> str:
        return self._run(widget_type, title, spec)
