"""네이버 스마트에디터에 초안을 입력한다.

로그인과 글쓰기 화면 열기는 사용자가 직접 한다. 봇은 자동화 표시 없이 띄운 일반 크롬에
디버깅 포트로 붙어서, 이미 열린 글쓰기 화면에 글만 입력한다. 발행 버튼은 절대 누르지 않는다.
"""
import os
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
    "map_search": ".se-place-search-keyword input, input.react-autosuggest__input",
    "map_result_add": ".se-place-map-search-result-item:first-child .se-place-add-button",
    "map_confirm": ".se-popup-button-confirm",
    "image_component": ".se-component.se-image",
    "align_button": "button.se-align-left-toolbar-button",
    "align_center": "button.se-toolbar-option-align-center-button",
}


class EditorError(Exception):
    pass


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


def _cursor_to_end(page, frame) -> None:
    frame.locator(SEL["body_text"]).last.click()
    page.keyboard.press("Control+End")


def _insert_map(page, frame, query: str) -> bool:
    try:
        frame.locator(SEL["map_button"]).click()
        search = frame.locator(SEL["map_search"]).first
        search.fill(query)
        search.press("Enter")
        frame.locator(SEL["map_result_add"]).first.click(timeout=8000)
        frame.locator(SEL["map_confirm"]).first.click(timeout=5000)
        return True
    except Exception:
        page.keyboard.press("Escape")
        return False


def _run(page, frame, act: tuple, warnings: list[str]) -> None:
    kind = act[0]
    if kind == "title":
        frame.locator(SEL["title"]).click()
        page.keyboard.insert_text(act[1])
        frame.locator(SEL["body_text"]).first.click()
    elif kind == "bold_line":
        page.keyboard.press("Control+b")
        page.keyboard.insert_text(act[1])
        page.keyboard.press("Control+b")
        page.keyboard.press("Enter")
    elif kind == "line":
        page.keyboard.insert_text(act[1])
        page.keyboard.press("Enter")
    elif kind == "enter":
        page.keyboard.press("Enter")
    elif kind == "quote":
        frame.locator(SEL["quote_button"]).click()
        page.keyboard.insert_text(act[1])
        _cursor_to_end(page, frame)
    elif kind == "photo":
        before = frame.locator(SEL["image_component"]).count()
        with page.expect_file_chooser() as fc:
            frame.locator(SEL["photo_button"]).click()
        fc.value.set_files(act[1])
        frame.locator(SEL["image_component"]).nth(before).wait_for(timeout=60_000)
        _cursor_to_end(page, frame)
    elif kind == "map":
        if not _insert_map(page, frame, act[1]):
            page.keyboard.insert_text(f"[지도: {act[1]}]")
            page.keyboard.press("Enter")
            warnings.append(f"지도를 자동으로 넣지 못했습니다. '[지도: {act[1]}]' 자리에 직접 넣어 주세요.")
        _cursor_to_end(page, frame)
    elif kind == "align_all_center":
        frame.locator(SEL["body_text"]).first.click()
        page.keyboard.press("Control+a")
        frame.locator(SEL["align_button"]).first.click()
        frame.locator(SEL["align_center"]).first.click()


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
