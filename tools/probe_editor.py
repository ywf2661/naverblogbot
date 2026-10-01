"""작성용 크롬에 붙어서 열린 글쓰기 화면의 툴바·입력 요소를 probe.txt에 기록한다.

사용법: 인자 없이 실행하면 작성용 크롬을 연다(로그인·글쓰기 화면은 직접). `record`를 붙여 실행하면 기록한다.
"""
import sys

import truststore

truststore.inject_into_ssl()

from playwright.sync_api import sync_playwright

from naverblogbot.editor import CDP_URL, SEL, find_write_page, open_browser

if len(sys.argv) < 2:
    open_browser()
    print("작성용 크롬을 열었습니다. 로그인 후 블로그 글쓰기 화면을 띄우세요.")
    sys.exit()

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP_URL)
    page = find_write_page(browser)
    frame = page.frame_locator(SEL["frame"])
    frame.locator(SEL["title"]).wait_for(timeout=15_000)
    out = [f"url: {page.url}"]
    for el in frame.locator(".se-toolbar button").all():
        out.append(f"{el.get_attribute('class')} | {el.get_attribute('data-name')} | {(el.inner_text() or '').strip()[:20]}")
    for key, sel in SEL.items():
        if key != "frame":
            out.append(f"{key}: {frame.locator(sel).count()}")
    open("probe.txt", "w", encoding="utf-8").write("\n".join(out))
    page.screenshot(path="probe.png")
    print("기록 완료")
