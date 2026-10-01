import html
import json
from pathlib import Path

from .draft import Draft, draft_to_dict
from .inputs import ReviewInput

_CSS = """body{font-family:'Malgun Gothic',sans-serif;max-width:720px;margin:24px auto;padding:0 16px;color:#222}
.post p{text-align:center;margin:0;line-height:1.8}.post .blank{height:1.8em}
.quote{text-align:center;border-left:4px solid #03c75a;margin:24px 0;padding:8px;font-weight:bold}
.post img{display:block;max-width:100%;margin:12px auto}.map{text-align:center;color:#03c75a;margin:12px}
.box{background:#f6f6f6;padding:12px 16px;border-radius:8px;margin-bottom:16px}.warn{background:#fff4e5}"""


def render_html(d: Draft, r: ReviewInput, warnings: list[str], items: list[str]) -> str:
    e = html.escape
    out = [f"<title>{e(r.store)} 초안</title><style>{_CSS}</style>"]
    if warnings:
        out.append("<div class='box warn'><b>경고</b><ul>" + "".join(f"<li>{e(w)}</li>" for w in warnings) + "</ul></div>")
    out.append("<div class='box'><b>발행 전 체크리스트</b><ul>" + "".join(f"<li>{e(i)}</li>" for i in items) + "</ul></div>")
    out.append("<div class='box'><b>제목 후보</b><ol>" + "".join(f"<li>{e(t)}</li>" for t in d.titles) + "</ol></div>")
    out.append("<div class='post'>")
    if d.disclosure:
        out.append(f"<p><b>{e(d.disclosure)}</b></p>")
    for b in d.blocks:
        if b.type == "quote":
            out.append(f"<div class='quote'>{e(b.text)}</div>")
        elif b.type == "lines":
            out.extend(f"<p>{e(x)}</p>" for x in b.lines)
        elif b.type == "blank":
            out.append("<div class='blank'></div>")
        elif b.type == "photo":
            out.append(f'<img src="{e(b.file)}" alt="{e(b.file)}">')
        elif b.type == "video":
            out.append(f"<div class='map'>[동영상: {e(b.file)}]</div>")
        elif b.type == "map":
            out.append(f"<div class='map'>[지도: {e(r.store)} {e(r.area)}]</div>")
    out.append(f"<p>{e(d.hashtag_line)}</p></div>")
    return "\n".join(out)


def save(d: Draft, r: ReviewInput, warnings: list[str], items: list[str]) -> Path:
    folder = Path(r.photo_dir)
    (folder / "draft.json").write_text(json.dumps(draft_to_dict(d), ensure_ascii=False, indent=2), encoding="utf-8")
    html_path = folder / "draft.html"
    html_path.write_text(render_html(d, r, warnings, items), encoding="utf-8")
    return html_path
