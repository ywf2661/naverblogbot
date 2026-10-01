import json, statistics as st
from collections import Counter
R=json.load(open("rows.json",encoding="utf-8"))
def q(xs):
    xs=sorted(xs); n=len(xs)
    if not n: return "-"
    return f"p25 {xs[n//4]} / med {xs[n//2]} / p75 {xs[3*n//4]} (n={n})"
def show(name,R):
    print(f"\n===== {name} ({len(R)})")
    for k in["title_len","imgs","chars","lines","blanks","emoji","video","map","sticker","quote","hr","stitle","bold","colored"]:
        print(k.ljust(10),q([r[k] for r in R]))
    print("tags".ljust(10),q([len(r["tags"]) for r in R]), " inline#",q([len(r["inline_tags"]) for r in R]))
    ll=[x for r in R for x in r["line_len"]]; print("line_len  ",q(ll))
    print("lines/blk ",q([x for r in R for x in r["blocks"]]))
    print("img run   ",q([x for r in R for x in r["runs"]]))
    print("txt btw img",q([x for r in R for x in r["text_between"]]))
    al=Counter();[al.update(r["align"]) for r in R]; print("align",al.most_common())
    domal=Counter(max(r["align"],key=r["align"].get) for r in R if r["align"]); print("dominant align per post",domal.most_common())
    fs=Counter();[fs.update(r["fs"]) for r in R]; print("fontsize",fs.most_common(8))
    ff=Counter();[ff.update(r["ff"]) for r in R]; print("font",ff.most_common(8))
    lh=Counter();[lh.update(r["lh"]) for r in R]; print("p style",lh.most_common(5))
    print("letter-spacing posts",sum(1 for r in R if r["letter_spacing"]))
    e=Counter();[e.update(r["ends"]) for r in R]; print("endings",e.most_common())
    em=Counter();[em.update(r["emojis"]) for r in R]; print("emoji top",em.most_common(25))
    print("posts w/ emoji>0", sum(1 for r in R if r["emoji"]))
show("ALL",R)
show("SPONSORED",[r for r in R if r["sponsored"]])
show("NOT SPONSORED",[r for r in R if not r["sponsored"]])
