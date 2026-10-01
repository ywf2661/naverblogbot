"""작성용 크롬을 열거나(인자 없음), 열린 글쓰기 탭의 툴바 버튼을 probe.txt에 기록한다(record)."""
import sys

from naverblogbot.cdp import connect_write_page
from naverblogbot.editor import DEBUG_PORT, open_browser

if len(sys.argv) < 2:
    open_browser()
    print("작성용 크롬을 열었습니다. 로그인 후 블로그 글쓰기 화면을 띄우세요.")
    sys.exit()

page = connect_write_page(DEBUG_PORT)
try:
    rows = page._q("return __all('.se-toolbar button', false).map(b => b.className + ' | ' + (b.dataset.name || '') + ' | ' + b.innerText.trim().slice(0, 20));")
    open("probe.txt", "w", encoding="utf-8").write("\n".join(rows))
    print("기록 완료")
finally:
    page.close()
