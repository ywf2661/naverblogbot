"""네이버 스마트에디터에 초안을 입력한다.

로그인과 글쓰기 화면 열기는 사용자가 직접 한다. 봇은 자동화 표시 없이 띄운 일반 크롬에
디버깅 포트로 붙어서, 이미 열린 글쓰기 화면에 글만 입력한다. 발행 버튼은 절대 누르지 않는다.
"""
import os
import re
import subprocess
from pathlib import Path

from .draft import Draft
from .inputs import ReviewInput
from .settings import profile_dir

DEBUG_PORT = 9333
CDP_URL = f"http://127.0.0.1:{DEBUG_PORT}"
START_URL = "https://blog.naver.com"
BROWSER_CANDIDATES = [
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
]

# 네이버가 화면을 바꾸면 여기만 고친다. tools/probe_editor.py로 확인한 값.
SEL = {
    "frame": "#mainFrame",
    "title": ".se-documentTitle .se-text-paragraph",
    "body_text": ".se-component.se-text .se-text-paragraph",
    "help_close": ".se-help-panel-close-button",
    "photo_button": "button.se-image-toolbar-button",
    "quote_button": "button.se-insert-quotation-default-toolbar-button",
    "map_button": "button.se-map-toolbar-button",
    "map_search": "input.react-autosuggest__input",
    "map_search_button": "button.se-place-search-button",
    "map_result_item": ".se-place-map-search-result-item",
    "map_result_link": ".se-place-map-search-result-link",
    "map_result_add": ".se-place-add-button",
    "map_confirm": ".se-popup-button-confirm",
    "popup_close": ".se-popup-close-button",
    "image_component": ".se-component.se-image",
    "align_button": "button[data-name='align-drop-down-with-justify']",  # 현재 정렬에 따라 클래스가 바뀌므로 data-name 사용
    "align_center": "button.se-toolbar-option-align-center-button",
    "bold_button": "button.se-bold-toolbar-button:visible",
}
STEP_MS = 150  # 줄 입력 사이 대기. 너무 빠르면 에디터가 입력을 놓친다.
COMPONENT_MS = 1000  # 인용구·지도·사진 삽입 후 대기


class EditorError(Exception):
    pass


_ASTRAL = re.compile("[𐀀-􏿿]|[^𐀀-􏿿]+")


def split_for_typing(text: str) -> list[str]:
    """에디터는 이모지와 글자를 한 번에 넣으면 이모지 뒤 글자를 버린다. 이모지를 따로 떼어 넣는다."""
    return _ASTRAL.findall(text)


def _type(page, text: str) -> None:
    for part in split_for_typing(text):
        page.keyboard.insert_text(part)
        page.wait_for_timeout(80)


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
    subprocess.Popen(browser_command(exe, profile_dir()))


def is_write_page(url: str) -> bool:
    return "Redirect=Write" in url or "/postwrite" in url or "PostWriteForm" in url


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


def _try_click(frame, selector: str, timeout: int = 1500) -> bool:
    try:
        frame.locator(selector).first.click(timeout=timeout)
        return True
    except Exception:
        return False


def _set_bold(frame, on: bool) -> None:
    btn = frame.locator(SEL["bold_button"]).first
    if ("se-is-selected" in (btn.get_attribute("class") or "")) != on:
        btn.click()


def _wait_uploaded(page, frame, index: int) -> None:
    img = frame.locator(SEL["image_component"]).nth(index).locator("img").first
    img.wait_for(timeout=60_000)
    for _ in range(120):  # 업로드가 끝나면 이미지 주소가 네이버 서버 주소로 바뀐다
        if (img.get_attribute("src") or "").startswith("https://"):
            return
        page.wait_for_timeout(500)
    raise EditorError("사진 업로드가 1분 안에 끝나지 않았습니다.")


def _insert_map(page, frame, query: str) -> bool:
    try:
        frame.locator(SEL["map_button"]).click()
        frame.locator(SEL["map_search"]).first.fill(query)
        frame.locator(SEL["map_search_button"]).first.click()
        item = frame.locator(SEL["map_result_item"]).first
        item.locator(SEL["map_result_link"]).click(timeout=8000)  # 결과를 골라야 [추가] 버튼이 보인다
        item.locator(SEL["map_result_add"]).click(timeout=5000)
        frame.locator(SEL["map_confirm"]).first.click(timeout=5000)
        return True
    except Exception:
        _try_click(frame, SEL["popup_close"])
        return False


def _run(page, frame, act: tuple, warnings: list[str]) -> None:
    kind = act[0]
    if kind == "title":
        frame.locator(SEL["title"]).click()
        _type(page, act[1])
        frame.locator(SEL["body_text"]).first.click()
        _set_bold(frame, False)  # 이전 작성에서 남은 굵게 상태를 끈다
    elif kind == "bold_line":
        _set_bold(frame, True)
        _type(page, act[1])
        page.keyboard.press("Enter")
        _set_bold(frame, False)
    elif kind == "line":
        _type(page, act[1])
        page.keyboard.press("Enter")
        page.wait_for_timeout(STEP_MS)
    elif kind == "enter":
        page.keyboard.press("Enter")
        page.wait_for_timeout(STEP_MS)
    elif kind == "quote":
        # 인용구 뒤에는 글 칸이 자동으로 생기지 않으므로 빈 줄을 하나 더 만들어 두고 그 위에 넣는다.
        page.keyboard.press("Enter")
        page.wait_for_timeout(STEP_MS)
        page.keyboard.press("ArrowUp")
        page.wait_for_timeout(STEP_MS)
        frame.locator(SEL["quote_button"]).click()
        page.wait_for_timeout(COMPONENT_MS)
        _type(page, act[1])
        page.wait_for_timeout(STEP_MS)
        page.keyboard.press("ArrowDown")  # 인용구의 출처 칸
        page.wait_for_timeout(STEP_MS)
        page.keyboard.press("ArrowDown")  # 인용구 아래 빈 줄
        page.wait_for_timeout(STEP_MS)
    elif kind == "photo":
        before = frame.locator(SEL["image_component"]).count()
        for attempt in range(3):  # 직전 사진 업로드 직후엔 버튼이 잠깐 반응하지 않을 때가 있다
            try:
                with page.expect_file_chooser(timeout=10_000) as fc:
                    frame.locator(SEL["photo_button"]).click()
                break
            except Exception:
                if attempt == 2:
                    raise
                page.keyboard.press("Escape")
                page.wait_for_timeout(1500)
        fc.value.set_files(act[1])
        _wait_uploaded(page, frame, before)
        page.wait_for_timeout(COMPONENT_MS)
        page.keyboard.press("ArrowDown")  # 사진 아래에 자동으로 생기는 빈 줄
    elif kind == "map":
        if not _insert_map(page, frame, act[1]):
            _type(page, f"[지도: {act[1]}]")
            page.keyboard.press("Enter")
            warnings.append(f"지도를 자동으로 넣지 못했습니다. '[지도: {act[1]}]' 자리에 직접 넣어 주세요.")
        else:
            page.wait_for_timeout(COMPONENT_MS)
            page.keyboard.press("ArrowDown")  # 지도 아래에 자동으로 생기는 빈 줄
    elif kind == "align_all_center":
        frame.locator(SEL["body_text"]).first.click()
        page.keyboard.press("Control+a")
        frame.locator(SEL["align_button"]).first.click()
        frame.locator(SEL["align_center"]).first.click()
        page.wait_for_timeout(STEP_MS)
        frame.locator(SEL["body_text"]).last.click()  # 전체 선택을 풀어서 이후 입력이 본문을 지우지 않게 한다


def find_write_page(browser):
    pages = [pg for ctx in browser.contexts for pg in ctx.pages if is_write_page(pg.url)]
    if not pages:
        raise EditorError("글쓰기 화면을 찾지 못했습니다. 작성용 크롬에서 블로그 [글쓰기]를 눌러 화면을 띄워 주세요.")
    return pages[-1]


def fill(d: Draft, r: ReviewInput, title: str, log=print, on_done=None) -> list[str]:
    from playwright.sync_api import sync_playwright

    warnings: list[str] = []
    acts = plan_actions(d, r, title)
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
        except Exception as e:
            raise EditorError("작성용 크롬이 열려 있지 않습니다. [작성용 크롬 열기]를 누르고 글쓰기 화면을 띄워 주세요.") from e
        page = find_write_page(browser)
        page.bring_to_front()
        frame = page.frame_locator(SEL["frame"])
        frame.locator(SEL["title"]).wait_for(timeout=15_000)
        _try_click(frame, SEL["help_close"])
        for i, act in enumerate(acts, 1):
            log(f"입력 중 {i}/{len(acts)}")
            try:
                _run(page, frame, act, warnings)
            except Exception as e:
                warnings.append(f"{i}번째 항목({act[0]}) 입력 중 멈췄습니다: {e}. 나머지는 draft.html을 보고 직접 넣어 주세요.")
                break
        log("입력을 마쳤습니다. 크롬에서 검토한 뒤 직접 발행하세요.")
    if on_done:
        on_done(warnings)
    return warnings
