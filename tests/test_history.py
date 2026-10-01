from naverblogbot.draft import Block, Draft
from naverblogbot.history import recent_phrases, remember


def d(first, last):
    return Draft(titles=[], blocks=[Block("lines", lines=first), Block("photo", file="a.jpg"), Block("lines", lines=last)],
                 tags=[], photos=[], confirm=[])


def test_empty_when_no_file(tmp_path):
    assert recent_phrases(tmp_path / "h.json") == []


def test_remember_first_and_last_lines(tmp_path):
    p = tmp_path / "h.json"
    remember(p, d(["안녕하세요", "오늘은", "판교", "중간"], ["끝1", "끝2", "끝3"]))
    assert recent_phrases(p) == ["안녕하세요", "오늘은", "판교", "끝1", "끝2", "끝3"]


def test_keeps_only_recent(tmp_path):
    p = tmp_path / "h.json"
    for i in range(5):
        remember(p, d([f"첫{i}"], [f"끝{i}"]), keep=3)
    phrases = recent_phrases(p)
    assert "첫0" not in phrases and "첫1" not in phrases
    assert "첫4" in phrases
