import anthropic
from PIL import Image

from naverblogbot.inputs import ReviewInput
from naverblogbot.pipeline import friendly_error, load_saved, make_draft
from naverblogbot.settings import Settings
from naverblogbot.writer import DraftError
from tests.test_writer import DRAFT_JSON, FakeClient


def test_make_draft_end_to_end(tmp_path):
    photos = tmp_path / "photos"
    photos.mkdir()
    Image.new("RGB", (50, 50)).save(photos / "a.jpg")
    r = ReviewInput(photos, "해미옥", "판교", "좋음", True, "리뷰노트")
    result = make_draft(r, Settings(api_key="k", mode="api"), FakeClient(), history_path=tmp_path / "h.json")
    assert result.draft.disclosure.startswith("[협찬]")
    assert result.html_path.exists()
    assert any("글자 수" in w for w in result.warnings)
    assert any("배너" in c for c in result.checklist)
    assert (tmp_path / "h.json").exists()
    assert load_saved(r).titles == DRAFT_JSON["titles"]


def test_friendly_error_auth():
    e = anthropic.AuthenticationError.__new__(anthropic.AuthenticationError)
    assert "API 키" in friendly_error(e)


def test_friendly_error_connection():
    e = anthropic.APIConnectionError.__new__(anthropic.APIConnectionError)
    assert "연결" in friendly_error(e)


def test_friendly_error_draft_and_unknown():
    assert friendly_error(DraftError("거절됨")) == "거절됨"
    assert "알 수 없는 오류" in friendly_error(ValueError("x"))


def _status_error(cls, message, status):
    e = cls.__new__(cls)
    e.message = message
    e.status_code = status
    return e


def test_friendly_error_credit_balance():
    e = _status_error(anthropic.BadRequestError, "Your credit balance is too low to access the Anthropic API.", 400)
    assert "잔액" in friendly_error(e)


def test_friendly_error_model_not_found():
    e = _status_error(anthropic.NotFoundError, "model: claude-opus-55", 404)
    assert "모델 이름" in friendly_error(e)


def test_friendly_error_other_bad_request_shows_reason():
    e = _status_error(anthropic.BadRequestError, "too many images", 400)
    msg = friendly_error(e)
    assert "too many images" in msg and "잠시 뒤" not in msg


def _photos(tmp_path):
    photos = tmp_path / "photos"
    photos.mkdir()
    Image.new("RGB", (50, 50)).save(photos / "a.jpg")
    return photos


def test_make_draft_looks_up_place_and_lists_it_in_checklist(tmp_path, monkeypatch):
    from naverblogbot import pipeline
    from naverblogbot.lookup import PlaceInfo
    seen = {}
    monkeypatch.setattr(pipeline, "lookup_place", lambda client, model, store, area: PlaceInfo(
        hours="매일 10~21시", parking="주차 가능", sources=["https://example.com/p"]))
    real_write = pipeline.write_draft

    def spy(*args, **kwargs):
        seen["place"] = kwargs.get("place")
        return real_write(*args, **kwargs)
    monkeypatch.setattr(pipeline, "write_draft", spy)
    r = ReviewInput(_photos(tmp_path), "도스마스", "여의도", "좋음", False)
    result = make_draft(r, Settings(api_key="k", mode="api"), FakeClient(), history_path=tmp_path / "h.json")
    assert seen["place"].hours == "매일 10~21시"
    assert any("검색으로 찾은" in c and "https://example.com/p" in c for c in result.checklist)


def test_make_draft_skips_lookup_when_user_typed_info_or_disabled(tmp_path, monkeypatch):
    from naverblogbot import pipeline
    called = []
    monkeypatch.setattr(pipeline, "lookup_place", lambda *a: called.append(1))
    r = ReviewInput(_photos(tmp_path), "도스마스", "여의도", "좋음", False, extra="주차 불가")
    make_draft(r, Settings(api_key="k", mode="api"), FakeClient(), history_path=tmp_path / "h.json")
    r2 = ReviewInput(r.photo_dir, "도스마스", "여의도", "좋음", False)
    make_draft(r2, Settings(api_key="k", mode="api"), FakeClient(), history_path=tmp_path / "h.json", lookup=False)
    assert called == []


def test_make_draft_lookup_failure_is_a_warning(tmp_path, monkeypatch):
    from naverblogbot import pipeline

    def boom(*a):
        raise RuntimeError("검색 서버 오류")
    monkeypatch.setattr(pipeline, "lookup_place", boom)
    r = ReviewInput(_photos(tmp_path), "도스마스", "여의도", "좋음", False)
    result = make_draft(r, Settings(api_key="k", mode="api"), FakeClient(), history_path=tmp_path / "h.json")
    assert any("자동 검색" in w for w in result.warnings)


def test_subscription_mode_uses_claude_code(tmp_path, monkeypatch):
    from naverblogbot import pipeline
    from naverblogbot.draft import draft_from_dict
    from naverblogbot.lookup import PlaceInfo
    calls = {}
    monkeypatch.setattr(pipeline.cc, "lookup_cc", lambda store, area, model: calls.setdefault("lookup", (store, model)) and PlaceInfo(parking="주차 가능"))
    def fake_write(r, paths, style, avoid, place=None, model=""):
        calls["write"] = (model, place.parking)
        return draft_from_dict(DRAFT_JSON)
    monkeypatch.setattr(pipeline.cc, "write_draft_cc", fake_write)
    r = ReviewInput(_photos(tmp_path), "도스마스", "여의도", "좋음", False)
    result = make_draft(r, Settings(mode="subscription", cc_model="sonnet"), None, history_path=tmp_path / "h.json")
    assert calls["lookup"] == ("도스마스", "sonnet") and calls["write"] == ("sonnet", "주차 가능")
    assert result.draft.titles == DRAFT_JSON["titles"]


def test_friendly_error_cc():
    from naverblogbot.cc import CCError
    assert friendly_error(CCError("구독 사용 한도에 도달했습니다.")) == "구독 사용 한도에 도달했습니다."
