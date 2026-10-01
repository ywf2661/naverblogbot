import json
from types import SimpleNamespace

import pytest
from PIL import Image

from naverblogbot.inputs import ReviewInput
from naverblogbot.writer import DraftError, SCHEMA, build_system, build_user_content, write_draft

DRAFT_JSON = {
    "titles": ["판교역 점심 맛집 해미옥 수육 후기"] * 3,
    "blocks": [{"type": "photo", "text": "", "lines": [], "file": "a.jpg"}],
    "tags": ["판교맛집"],
    "photos": [{"file": "a.jpg", "kind": "food", "has_face": False}],
    "confirm": [],
}


class FakeStream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.message


class FakeClient:
    def __init__(self, text=json.dumps(DRAFT_JSON, ensure_ascii=False), stop_reason="end_turn"):
        self.calls = []
        msg = SimpleNamespace(stop_reason=stop_reason, content=[
            SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)])
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))
        self._msg = msg

    def _stream(self, **kwargs):
        self.calls.append(kwargs)
        return FakeStream(self._msg)


@pytest.fixture
def setup(tmp_path):
    Image.new("RGB", (50, 50)).save(tmp_path / "a.jpg")
    r = ReviewInput(tmp_path, "해미옥", "판교", "수육이 부드러웠음", True, "리뷰노트",
                    menu="수육 정식 15,000원", keywords="판교맛집")
    return r, [tmp_path / "a.jpg"]


def test_system_includes_rules_and_style():
    s = build_system("저는 ~했어용 말투")
    assert "22자" in s and "1,500~2,300자" in s
    assert "저는 ~했어용 말투" in s
    assert "<내 글 예시>" not in build_system("")


def test_user_content_has_memo_and_labeled_images(setup):
    r, paths = setup
    content = build_user_content(r, paths, avoid=["안녕하세요 여러분"])
    memo = content[0]["text"]
    assert "해미옥" in memo and "수육 정식 15,000원" in memo and "판교맛집" in memo
    assert "안녕하세요 여러분" in memo
    assert "협찬" in memo
    assert content[1] == {"type": "text", "text": "사진 파일명: a.jpg"}
    assert content[2]["type"] == "image" and content[2]["source"]["media_type"] == "image/jpeg"


def test_write_draft_request_shape(setup):
    r, paths = setup
    client = FakeClient()
    d = write_draft(client, "claude-opus-5", r, paths, "", [])
    assert d.titles[0].startswith("판교역")
    call = client.calls[0]
    assert call["model"] == "claude-opus-5"
    assert call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["extra_body"] == {"fallbacks": "default"}
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"]["format"] == {"type": "json_schema", "schema": SCHEMA}


def test_refusal_raises(setup):
    r, paths = setup
    with pytest.raises(DraftError, match="거절"):
        write_draft(FakeClient(stop_reason="refusal"), "m", r, paths, "", [])


def test_bad_json_raises(setup):
    r, paths = setup
    with pytest.raises(DraftError, match="형식"):
        write_draft(FakeClient(text="{not json"), "m", r, paths, "", [])


def test_uses_last_text_block_after_fallback(setup):
    r, paths = setup
    client = FakeClient()
    client._msg.content = [
        SimpleNamespace(type="thinking", thinking=""),
        SimpleNamespace(type="text", text='{"titles": ["부분'),
        SimpleNamespace(type="fallback"),
        SimpleNamespace(type="text", text=json.dumps(DRAFT_JSON, ensure_ascii=False)),
    ]
    assert write_draft(client, "m", r, paths, "", []).titles == DRAFT_JSON["titles"]
