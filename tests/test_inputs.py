from pathlib import Path

from naverblogbot.inputs import ReviewInput, missing_judgments, validate


def make(tmp_path, **kw):
    base = dict(photo_dir=tmp_path, store="해미옥", area="판교", impression="수육이 부드러웠음", sponsored=False)
    base.update(kw)
    return ReviewInput(**base)


def touch(folder: Path, *names):
    for n in names:
        (folder / n).write_bytes(b"x")


def test_valid_input_has_no_errors(tmp_path):
    touch(tmp_path, "a.jpg")
    assert validate(make(tmp_path)) == []


def test_required_fields(tmp_path):
    touch(tmp_path, "a.jpg")
    errors = validate(make(tmp_path, store=" ", area="", impression=""))
    assert "가게명을 입력하세요." in errors
    assert "동네를 입력하세요." in errors
    assert "한 줄 소감을 입력하세요." in errors


def test_sponsored_requires_sponsor(tmp_path):
    touch(tmp_path, "a.jpg")
    assert "협찬이면 업체명(또는 체험단명)을 입력하세요." in validate(make(tmp_path, sponsored=True))


def test_missing_folder(tmp_path):
    errors = validate(make(tmp_path / "없음"))
    assert errors == ["사진 폴더를 찾을 수 없습니다."]


def test_validate_heic_only(tmp_path):
    touch(tmp_path, "a.HEIC", "b.heic")
    errors = validate(make(tmp_path))
    assert any("HEIC" in e and "JPG" in e for e in errors)


def test_no_photos(tmp_path):
    touch(tmp_path, "memo.txt")
    assert "폴더에 사진(jpg, png, webp)이 없습니다." in validate(make(tmp_path))


def test_keyword_list():
    r = ReviewInput(Path("."), "s", "a", "i", True, "x", keywords=" 판교맛집, ,해미옥 ,")
    assert r.keyword_list == ["판교맛집", "해미옥"]


def test_missing_judgments(tmp_path):
    assert missing_judgments(make(tmp_path)) == ["아쉬운 점", "추천 대상"]
    assert missing_judgments(make(tmp_path, cons="짰음", target="직장인")) == []
