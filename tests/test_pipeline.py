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
    result = make_draft(r, Settings(api_key="k"), FakeClient(), history_path=tmp_path / "h.json")
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
