import json
from pathlib import Path

from naverblogbot.draft import Block, Draft, PhotoInfo
from naverblogbot.inputs import ReviewInput
from naverblogbot.preview import render_html, save


def sample():
    return Draft(titles=["제목<1>", "제목2", "제목3"],
                 blocks=[Block("quote", text="📍 위치"), Block("lines", lines=["줄 하나", "줄 둘"]),
                         Block("blank"), Block("photo", file="a.jpg"), Block("map")],
                 tags=["판교맛집"], photos=[PhotoInfo("a.jpg", "food", False)], confirm=[],
                 disclosure="[협찬] 이 글은 리뷰노트로부터 식사를 무상으로 제공받아 작성했습니다.")


def test_render_html_contents():
    r = ReviewInput(Path("."), "해미옥", "판교", "좋음", True, "리뷰노트")
    html = render_html(sample(), r, ["경고 하나"], ["확인 하나"])
    assert "제목&lt;1&gt;" in html
    assert '<img src="a.jpg"' in html
    assert "<b>[협찬]" in html
    assert "경고 하나" in html and "확인 하나" in html
    assert "#판교맛집" in html
    assert "지도" in html


def test_save_writes_files(tmp_path):
    r = ReviewInput(tmp_path, "해미옥", "판교", "좋음", False)
    html_path = save(sample(), r, [], [])
    assert html_path == tmp_path / "draft.html"
    assert json.loads((tmp_path / "draft.json").read_text(encoding="utf-8"))["titles"][1] == "제목2"


def test_render_html_shows_video_placeholder():
    d = sample()
    d.blocks.append(Block("video", file="v.mov"))
    html = render_html(d, ReviewInput(Path("."), "해미옥", "판교", "좋음", False), [], [])
    assert "[동영상: v.mov]" in html
