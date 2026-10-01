"""가게 영업시간·휴무일·주차를 Claude 웹 검색으로 찾는다. 못 찾으면 빈 값을 돌려준다."""
import json
from dataclasses import dataclass, field

SCHEMA = {
    "type": "object",
    "properties": {
        "location": {"type": "string"},
        "hours": {"type": "string"},
        "closed": {"type": "string"},
        "parking": {"type": "string"},
        "sources": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["location", "hours", "closed", "parking", "sources"],
    "additionalProperties": False,
}

PROMPT = """웹 검색으로 '{store}'의 {area} 매장 정보를 찾아라. 지점이 여러 곳이면 {area}에 있는 매장만.
- location: 찾아가는 길. 가까운 역·출구와 도보 시간, 건물·층 (예: "여의도역 3번 출구 도보 5분, ○○빌딩 지하 1층")
- hours: 요일별 영업시간, 브레이크타임, 라스트오더. 블로그에 그대로 옮길 수 있게 짧게 (예: "평일 10:00~21:00 (브레이크 14:00~17:00, 라스트오더 20:50) / 토 10:00~14:00")
- closed: 정기 휴무일. 휴무가 없으면 "연중무휴", 모르면 빈 문자열
- parking: 주차 가능 여부와 조건 (예: "건물 지하주차장 1시간 무료"). 모르면 빈 문자열
- sources: 참고한 페이지 주소
네이버 플레이스, 카카오맵, 매장 공식 SNS, 최근 방문 후기를 우선한다. 확실하지 않은 항목은 지어내지 말고 빈 문자열로 둔다."""


@dataclass
class PlaceInfo:
    location: str = ""
    hours: str = ""
    closed: str = ""
    parking: str = ""
    sources: list[str] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return bool(self.location or self.hours or self.closed or self.parking)

    def memo(self) -> str:
        parts = [("위치", self.location), ("영업시간", self.hours), ("휴무", self.closed), ("주차", self.parking)]
        return ", ".join(f"{k}: {v}" for k, v in parts if v)


def lookup_place(client, model: str, store: str, area: str, max_continuations: int = 3) -> PlaceInfo:
    question = {"role": "user", "content": PROMPT.format(store=store, area=area)}
    messages = [question]
    for _ in range(max_continuations + 1):
        with client.beta.messages.stream(
            model=model,
            max_tokens=8000,
            betas=["server-side-fallback-2026-07-01"],
            extra_body={"fallbacks": "default"},
            thinking={"type": "adaptive"},
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}],
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},  # low는 검색을 거의 안 해서 빈 값이 나왔다
            messages=messages,
        ) as stream:
            message = stream.get_final_message()
        if message.stop_reason != "pause_turn":
            break
        # 서버 쪽 검색이 길어지면 멈춘다. 같은 대화를 다시 보내면 이어서 진행한다.
        messages = [question, {"role": "assistant", "content": message.content}]
    if message.stop_reason == "refusal":
        return PlaceInfo()
    text = next((b.text for b in reversed(message.content) if b.type == "text"), "")
    try:
        data = json.loads(text)
        return PlaceInfo(location=data["location"], hours=data["hours"], closed=data["closed"],
                         parking=data["parking"], sources=list(data["sources"]))
    except (json.JSONDecodeError, KeyError, TypeError):
        return PlaceInfo()
