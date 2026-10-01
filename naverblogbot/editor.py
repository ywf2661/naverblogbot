"""네이버 스마트에디터에 초안을 입력한다.

로그인과 글쓰기 화면 열기는 사용자가 직접 한다. 봇은 자동화 표시 없이 띄운 일반 크롬의
'글쓰기 탭 하나'에만 개발자 도구 프로토콜로 붙어서 글만 입력한다(cdp.py). 발행 버튼은 절대 누르지 않는다.
"""
import os
import re
import subprocess
from pathlib import Path

from .cdp import CDPError, CDPPage, connect_write_page, is_write_page  # noqa: F401  (is_write_page는 다른 곳에서 씀)
from .draft import Draft
from .inputs import ReviewInput
from .settings import profile_dir

DEBUG_PORT = 9333
START_URL = "https://blog.naver.com"
BROWSER_CANDIDATES = [
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
]

# 네이버가 화면을 바꾸면 여기만 고친다. 2026-10-01 실제 에디터에서 확인한 값.
SEL = {
    "title": ".se-documentTitle .se-text-paragraph",
    "body_text": ".se-component.se-text .se-text-paragraph",
    "all_text": ".se-documentTitle .se-text-paragraph, .se-component .se-text-paragraph",
    "placeholder": ".se-placeholder",
    "help_close": ".se-help-panel-close-button",
    "photo_button": "button.se-image-toolbar-button",
    "quote_button": "button.se-insert-quotation-default-toolbar-button",
    "map_button": "button.se-map-toolbar-button",
    "map_search": "input.react-autosuggest__input",
    "map_search_button": "button.se-place-search-button",
    "map_result_link": ".se-place-map-search-result-link",
    "map_result_add": ".se-place-add-button",
    "map_confirm": ".se-popup-button-confirm",
    "popup_close": ".se-popup-close-button",
    "image_component": ".se-component.se-image",
    "image_img": ".se-component.se-image img",
    "align_button": "button[data-name='align-drop-down-with-justify']",  # 현재 정렬에 따라 클래스가 바뀌므로 data-name 사용
    "align_center": "button.se-toolbar-option-align-center-button",
    "bold_button": "button.se-bold-toolbar-button",
}
STEP_MS = 150  # 줄 입력 사이 대기. 너무 빠르면 에디터가 입력을 놓친다.
COMPONENT_MS = 1000  # 인용구·지도·사진 삽입 후 대기
CLICK_MS = 300  # 클릭 직후 바로 입력하면 첫 글자가 사라진다


class EditorError(Exception):
    pass


_ASTRAL = re.compile("[\U00010000-\U0010FFFF]|[^\U00010000-\U0010FFFF]+")


def split_for_typing(text: str) -> list[str]:
    """에디터는 이모지와 글자를 한 번에 넣으면 이모지 뒤 글자를 버린다. 이모지를 따로 떼어 넣는다."""
    return _ASTRAL.findall(text)


def find_browser(candidates: list[str] = BROWSER_CANDIDATES) -> Path | None:
    for c in candidates:
        p = Path(os.path.expandvars(c))
        if p.is_file():
            return p
    return None


def browser_command(exe: Path, profile: Path, port: int = DEBUG_PORT) -> list[str]:
    return [str(exe), f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
            "--no-first-run", "--no-default-browser-check", START_URL]


def open_browser() -> None:
    exe = find_browser()
    if not exe:
        raise EditorError("크롬이나 엣지를 찾을 수 없습니다. 크롬을 설치해 주세요.")
    try:
        subprocess.Popen(browser_command(exe, profile_dir()))
    except OSError as e:
        raise EditorError(f"크롬을 실행하지 못했습니다: {e}") from e


def is_blank_editor(texts: list[str]) -> bool:
    return all(not t.replace("​", "").strip() for t in texts)


def plan_actions(d: Draft, r: ReviewInput, title: str) -> list[tuple]:
    folder = Path(r.photo_dir)
    acts: list[tuple] = [("title", title)]
    if d.disclosure:
        acts.append(("bold_line", d.disclosure))
    for b in d.blocks:
        if b.type == "lines":
            acts.extend(("line", x) for x in b.lines)
        elif b.type == "blank":
            acts.append(("enter",))
        elif b.type == "quote":
            acts.append(("quote", b.text))
        elif b.type == "map":
            acts.append(("map", f"{r.store} {r.area}"))
        elif b.type == "photo" and (folder / b.file).is_file():
            acts.append(("photo", str(folder / b.file)))
    acts.append(("line", d.hashtag_line))
    acts.append(("align_all_center",))
    return acts


def _type(page: CDPPage, text: str) -> None:
    for part in split_for_typing(text):
        page.insert_text(part)
        page.sleep(80)


def _try_click(page: CDPPage, sel: str, timeout: float = 1.5) -> bool:
    try:
        page.click(sel, timeout=timeout)
        return True
    except CDPError:
        return False


def _set_bold(page: CDPPage, on: bool) -> None:
    cls = page.attr(SEL["bold_button"], "class", visible=True) or ""
    if ("se-is-selected" in cls) != on:
        page.click(SEL["bold_button"])
    page.sleep(CLICK_MS)


def _wait_uploaded(page: CDPPage, index: int) -> None:
    page.wait_for(SEL["image_img"], index, visible=False, timeout=60)
    for _ in range(120):  # 업로드가 끝나면 이미지 주소가 네이버 서버 주소로 바뀐다
        if (page.attr(SEL["image_img"], "src", index) or "").startswith("https://"):
            return
        page.sleep(500)
    raise EditorError("사진 업로드가 1분 안에 끝나지 않았습니다.")


def _insert_map(page: CDPPage, query: str) -> bool:
    try:
        page.click(SEL["map_button"])
        page.sleep(COMPONENT_MS)  # 장소 창이 다 열리기 전에 입력하면 검색어가 사라진다
        page.fill(SEL["map_search"], query)
        page.sleep(CLICK_MS)
        page.click(SEL["map_search_button"])
        page.click(SEL["map_result_link"], timeout=8)  # 결과를 골라야 [추가] 버튼이 보인다
        page.sleep(CLICK_MS * 2)
        page.click(SEL["map_result_add"], timeout=5)
        page.sleep(CLICK_MS * 2)
        page.click(SEL["map_confirm"], timeout=5)
        return True
    except CDPError:
        _try_click(page, SEL["popup_close"])
        return False


def _run(page: CDPPage, act: tuple, warnings: list[str]) -> None:
    kind = act[0]
    if kind == "title":
        page.click(SEL["title"])
        page.sleep(CLICK_MS)
        _type(page, act[1])
        page.click(SEL["body_text"])
        page.sleep(CLICK_MS)
        _set_bold(page, False)  # 이전 작성에서 남은 굵게 상태를 끈다
    elif kind == "bold_line":
        _set_bold(page, True)
        _type(page, act[1])
        page.press("Enter")
        _set_bold(page, False)
    elif kind == "line":
        _type(page, act[1])
        page.press("Enter")
        page.sleep(STEP_MS)
    elif kind == "enter":
        page.press("Enter")
        page.sleep(STEP_MS)
    elif kind == "quote":
        # 인용구 뒤에는 글 칸이 자동으로 생기지 않으므로 빈 줄을 하나 더 만들어 두고 그 위에 넣는다.
        page.press("Enter")
        page.sleep(STEP_MS)
        page.press("ArrowUp")
        page.sleep(STEP_MS)
        page.click(SEL["quote_button"])
        page.sleep(COMPONENT_MS)
        _type(page, act[1])
        page.sleep(STEP_MS)
        page.press("ArrowDown")  # 인용구의 출처 칸
        page.sleep(STEP_MS)
        page.press("ArrowDown")  # 인용구 아래 빈 줄
        page.sleep(STEP_MS)
    elif kind == "photo":
        before = page.count(SEL["image_component"])
        for attempt in range(3):  # 직전 사진 업로드 직후엔 버튼이 잠깐 반응하지 않을 때가 있다
            try:
                page.choose_file(SEL["photo_button"], act[1], timeout=10)
                break
            except CDPError:
                if attempt == 2:
                    raise
                page.press("Escape")
                page.sleep(1500)
        _wait_uploaded(page, before)
        page.sleep(COMPONENT_MS)
        page.press("ArrowDown")  # 사진 아래에 자동으로 생기는 빈 줄
    elif kind == "map":
        if not _insert_map(page, act[1]):
            _type(page, f"[지도: {act[1]}]")
            page.press("Enter")
            warnings.append(f"지도를 자동으로 넣지 못했습니다. '[지도: {act[1]}]' 자리에 직접 넣어 주세요.")
        else:
            page.sleep(COMPONENT_MS)
            page.press("ArrowDown")  # 지도 아래에 자동으로 생기는 빈 줄
    elif kind == "align_all_center":
        page.click(SEL["body_text"])
        page.press("Control+a")
        page.click(SEL["align_button"])
        page.click(SEL["align_center"])
        page.sleep(STEP_MS)
        page.click(SEL["body_text"], index=-1)  # 전체 선택을 풀어서 이후 입력이 본문을 지우지 않게 한다


def fill(d: Draft, r: ReviewInput, title: str, log=print, on_done=None) -> list[str]:
    warnings: list[str] = []
    acts = plan_actions(d, r, title)
    try:
        page = connect_write_page(DEBUG_PORT)
    except CDPError as e:
        raise EditorError(f"{e} [① 작성용 크롬 열기]로 연 크롬에서 블로그 [글쓰기] 화면을 띄워 주세요.") from e
    try:
        try:
            page.wait_for(SEL["title"], timeout=15)
        except CDPError as e:
            raise EditorError("글쓰기 화면의 제목 칸을 찾지 못했습니다. 블로그 [글쓰기] 화면을 다시 띄워 주세요.") from e
        if not is_blank_editor(page.texts(SEL["all_text"], drop=SEL["placeholder"])):
            raise EditorError("글쓰기 화면이 비어 있지 않습니다. 이전 내용을 지우거나 새 글쓰기 화면을 띄운 뒤 다시 눌러 주세요.")
        _try_click(page, SEL["help_close"])
        for i, act in enumerate(acts, 1):
            log(f"입력 중 {i}/{len(acts)}")
            try:
                _run(page, act, warnings)
            except (CDPError, EditorError) as e:
                warnings.append(f"{i}번째 항목({act[0]}) 입력 중 멈췄습니다: {e} 나머지는 draft.html을 보고 직접 넣어 주세요.")
                break
        log("입력을 마쳤습니다. 크롬에서 검토한 뒤 직접 발행하세요.")
    finally:
        page.close()
    if on_done:
        on_done(warnings)
    return warnings
