import json
from types import SimpleNamespace

from naverblogbot.lookup import PlaceInfo, lookup_place
from tests.test_writer import FakeStream

FOUND = {"location": "여의도역 3번 출구 도보 5분, 지하 1층", "hours": "매일 10:00~21:00 (브레이크타임 14:00~17:00)", "closed": "", "parking": "주차 가능",
         "sources": ["https://www.diningcode.com/x"]}


class SeqClient:
    """호출마다 준비된 응답을 차례로 돌려주는 가짜 클라이언트."""

    def __init__(self, messages):
        self.calls = []
        self._messages = list(messages)
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kwargs):
        self.calls.append(kwargs)
        return FakeStream(self._messages.pop(0))


def msg(stop, *blocks):
    return SimpleNamespace(stop_reason=stop, content=list(blocks))


def text(t):
    return SimpleNamespace(type="text", text=t)


def test_lookup_parses_and_uses_web_search():
    client = SeqClient([msg("end_turn", SimpleNamespace(type="server_tool_use"), text(json.dumps(FOUND, ensure_ascii=False)))])
    info = lookup_place(client, "claude-opus-5", "도스마스", "여의도")
    assert info == PlaceInfo(**FOUND)
    call = client.calls[0]
    assert call["tools"][0]["type"] == "web_search_20260209"
    assert "도스마스" in call["messages"][0]["content"] and "여의도" in call["messages"][0]["content"]
    assert call["output_config"]["effort"] == "medium"


def test_lookup_resumes_after_pause_turn():
    paused = msg("pause_turn", SimpleNamespace(type="server_tool_use"))
    client = SeqClient([paused, msg("end_turn", text(json.dumps(FOUND, ensure_ascii=False)))])
    assert lookup_place(client, "m", "도스마스", "여의도").parking == "주차 가능"
    second = client.calls[1]["messages"]
    assert second[1] == {"role": "assistant", "content": paused.content}
    assert len(second) == 2


def test_lookup_refusal_or_bad_json_returns_empty():
    assert not lookup_place(SeqClient([msg("refusal")]), "m", "a", "b").found
    assert not lookup_place(SeqClient([msg("end_turn", text("{oops"))]), "m", "a", "b").found


def test_place_info_memo():
    info = PlaceInfo(**FOUND)
    assert info.found
    assert "영업시간: 매일 10:00~21:00" in info.memo() and "주차: 주차 가능" in info.memo()
    assert "위치: 여의도역 3번 출구" in info.memo()
    assert "휴무" not in info.memo()
    assert not PlaceInfo().found
