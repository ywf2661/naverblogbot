from pathlib import Path

from naverblogbot.draft import (Block, Draft, PhotoInfo, body_char_count, check, checklist,
                                disclosure_text, draft_from_dict, draft_to_dict, finalize, wrap_line)
from naverblogbot.inputs import ReviewInput


def review(**kw):
    base = dict(photo_dir=Path("."), store="해미옥", area="판교", impression="좋음", sponsored=False)
    base.update(kw)
    return ReviewInput(**base)


def sample(lines=None, photos=("a.jpg",), tags=None):
    blocks = [Block("quote", text="📍 위치"), Block("lines", lines=lines or ["판교역에서 가까워요"]), Block("map")]
    blocks += [Block("photo", file=f) for f in photos]
    return Draft(titles=["판교 맛집 해미옥"], blocks=blocks, tags=tags or ["판교맛집"] * 12,
                 photos=[PhotoInfo(f, "food", False) for f in photos], confirm=[])


def test_wrap_line_short_unchanged():
    assert wrap_line("판교역에서 가까워요") == ["판교역에서 가까워요"]


def test_wrap_line_splits_on_spaces():
    out = wrap_line("점심시간에 직장인들이 줄을 서서 기다리는 모습이 인상적이었어요")
    assert all(len(x) <= 22 for x in out)
    assert " ".join(out) == "점심시간에 직장인들이 줄을 서서 기다리는 모습이 인상적이었어요"


def test_wrap_line_hard_split():
    s = "경기성남시분당구판교역로192번길16일층해미옥판교본점"
    out = wrap_line(s)
    assert all(len(x) <= 22 for x in out)
    assert "".join(out) == s


def test_disclosure_josa():
    assert disclosure_text("리뷰노트") == "[협찬] 이 글은 리뷰노트로부터 식사를 무상으로 제공받아 작성했습니다."
    assert disclosure_text("강남맛집") == "[협찬] 이 글은 강남맛집으로부터 식사를 무상으로 제공받아 작성했습니다."
    assert disclosure_text("디너의여왕 체험단") == "[협찬] 이 글은 디너의여왕 체험단으로부터 식사를 무상으로 제공받아 작성했습니다."
    assert disclosure_text("서울") == "[협찬] 이 글은 서울로부터 식사를 무상으로 제공받아 작성했습니다."
    assert disclosure_text("REVU") == "[협찬] 이 글은 REVU(으)로부터 식사를 무상으로 제공받아 작성했습니다."


def test_finalize_wraps_and_adds_disclosure():
    d = finalize(sample(lines=["점심시간에 직장인들이 줄을 서서 기다리는 모습이 인상적이었어요"]),
                 review(sponsored=True, sponsor="리뷰노트"))
    assert d.disclosure.startswith("[협찬] 이 글은 리뷰노트로부터")
    assert all(len(x) <= 22 for b in d.blocks for x in b.lines)


def test_finalize_no_disclosure_when_not_sponsored():
    assert finalize(sample(), review()).disclosure == ""


def test_hashtag_line():
    d = sample(tags=["판교맛집", "#해미옥", " "])
    assert d.hashtag_line == "#판교맛집 #해미옥"


def test_body_char_count_excludes_spaces_and_hashtags():
    d = sample(lines=["가 나", "다"])
    d.disclosure = "광고 문구"
    # "📍 위치"(3) + "가나"(2) + "다"(1) + "광고문구"(4)
    assert body_char_count(d) == 10


def test_dict_roundtrip():
    d = sample()
    assert draft_from_dict(draft_to_dict(d)) == d


def test_check_short_and_few_photos():
    warnings = check(sample(), review(), ["a.jpg"])
    assert any("글자 수" in w and "1,100" in w for w in warnings)
    assert any("사진이 1장" in w for w in warnings)


def test_check_photo_mismatch():
    d = sample(photos=("a.jpg", "zzz.jpg"))
    warnings = check(d, review(), ["a.jpg", "b.jpg"])
    assert any("b.jpg" in w and "빠졌" in w for w in warnings)
    assert any("zzz.jpg" in w and "없는" in w for w in warnings)


def test_check_missing_keywords():
    warnings = check(sample(), review(keywords="판교맛집, 수육맛집"), ["a.jpg"])
    assert any("수육맛집" in w for w in warnings)
    assert not any("'판교맛집'" in w for w in warnings)


def test_check_too_many_emoji():
    d = sample(lines=["😀" * 13])
    assert any("이모지" in w for w in check(d, review(), ["a.jpg"]))


def test_checklist_items():
    d = sample()
    d.photos = [PhotoInfo("a.jpg", "food", True)]
    d.confirm = ["돈가스 12,000원"]
    items = checklist(d, review(sponsored=True, sponsor="리뷰노트"))
    assert any("배너" in i for i in items)
    assert any("광고 문구" in i and "크기" in i for i in items)
    assert any("a.jpg" in i and "모자이크" in i for i in items)
    assert any("돈가스 12,000원" in i for i in items)
    assert any("지도" in i for i in items)
    assert not any("배너" in i for i in checklist(d, review()))


def test_finalize_collapses_blank_blocks():
    d = sample()
    d.blocks = [Block("blank"), Block("lines", lines=["a"]), Block("blank"), Block("blank"), Block("blank"),
                Block("lines", lines=["b"]), Block("blank"), Block("blank")]
    kinds = [b.type for b in finalize(d, review()).blocks]
    assert kinds == ["lines", "blank", "lines"]


def test_check_counts_videos_as_media():
    d = sample(photos=("a.jpg",))
    d.blocks.append(Block("video", file="v.mov"))
    assert not any("v.mov" in w for w in check(d, review(), ["a.jpg", "v.mov"]))
    assert any("v.mov" in w and "빠졌" in w for w in check(sample(), review(), ["a.jpg", "v.mov"]))


def test_finalize_brackets_confirm_items():
    d = sample(lines=["확인: 비프부리또 9,000원", "「확인: 치킨부리또 8,000원」이에요"])
    d.confirm = ["비프부리또 9,000원", "치킨부리또 8,000원"]
    lines = [x for b in finalize(d, review()).blocks for x in b.lines]
    assert "「확인: 비프부리또 9,000원」" in lines
    assert "「확인: 치킨부리또 8,000원」이에요" in lines  # 이미 괄호가 있으면 그대로
