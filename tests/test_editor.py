from naverblogbot.draft import Block, Draft
from naverblogbot.editor import plan_actions
from naverblogbot.inputs import ReviewInput


def make(tmp_path, sponsored=False):
    (tmp_path / "a.jpg").write_bytes(b"x")
    d = Draft(titles=["t"], tags=["판교맛집", "해미옥"], photos=[], confirm=[],
              blocks=[Block("lines", lines=["첫 줄", "둘째 줄"]), Block("blank"), Block("quote", text="📍 위치"),
                      Block("map"), Block("photo", file="a.jpg"), Block("photo", file="없음.jpg")],
              disclosure="[협찬] 문구" if sponsored else "")
    r = ReviewInput(tmp_path, "해미옥", "판교", "좋음", sponsored, "리뷰노트" if sponsored else "")
    return d, r


def test_plan_actions_order(tmp_path):
    d, r = make(tmp_path)
    acts = plan_actions(d, r, "선택한 제목")
    assert acts == [
        ("title", "선택한 제목"),
        ("line", "첫 줄"), ("line", "둘째 줄"),
        ("enter",),
        ("quote", "📍 위치"),
        ("map", "해미옥 판교"),
        ("photo", str(tmp_path / "a.jpg")),
        ("line", "#판교맛집 #해미옥"),
        ("align_all_center",),
    ]


def test_plan_actions_disclosure_first(tmp_path):
    d, r = make(tmp_path, sponsored=True)
    acts = plan_actions(d, r, "t")
    assert acts[1] == ("bold_line", "[협찬] 문구")


def test_plan_actions_skips_unknown_photo(tmp_path):
    d, r = make(tmp_path)
    assert not any(a[0] == "photo" and "없음.jpg" in a[1] for a in plan_actions(d, r, "t"))


def test_find_browser_picks_first_existing(tmp_path, monkeypatch):
    from naverblogbot.editor import find_browser
    monkeypatch.setenv("TESTDIR", str(tmp_path))
    (tmp_path / "chrome.exe").write_bytes(b"x")
    assert find_browser([r"%TESTDIR%\none.exe", r"%TESTDIR%\chrome.exe"]) == tmp_path / "chrome.exe"


def test_find_browser_none(tmp_path):
    from naverblogbot.editor import find_browser
    assert find_browser([str(tmp_path / "none.exe")]) is None


def test_browser_command_has_no_automation_flags(tmp_path):
    from naverblogbot.editor import DEBUG_PORT, browser_command
    cmd = browser_command(tmp_path / "chrome.exe", tmp_path / "profile")
    assert cmd[0] == str(tmp_path / "chrome.exe")
    assert f"--remote-debugging-port={DEBUG_PORT}" in cmd
    assert f"--user-data-dir={tmp_path / 'profile'}" in cmd
    assert not any("automation" in c for c in cmd)
    assert cmd[-1] == "https://blog.naver.com"


def test_is_write_page():
    from naverblogbot.editor import is_write_page
    assert is_write_page("https://blog.naver.com/ywf2661?Redirect=Write&")
    assert is_write_page("https://blog.naver.com/ywf2661/postwrite")
    assert not is_write_page("https://blog.naver.com/ywf2661")
    assert not is_write_page("https://www.naver.com")


def test_split_for_typing_isolates_emoji():
    from naverblogbot.editor import split_for_typing
    assert split_for_typing("📍 위치·정보") == ["📍", " 위치·정보"]
    assert split_for_typing("맛있다😋😋 끝") == ["맛있다", "😋", "😋", " 끝"]
    assert split_for_typing("✔ 직장인 점심") == ["✔ 직장인 점심"]
    assert split_for_typing("") == []


def test_is_blank_editor():
    from naverblogbot.editor import is_blank_editor
    assert is_blank_editor(["", "\u200b", "  "])
    assert not is_blank_editor(["", "이전 글 내용"])
