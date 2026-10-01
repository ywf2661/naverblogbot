import json, re, glob
from bs4 import BeautifulSoup
R=json.load(open("rows.json",encoding="utf-8"))
DISC=re.compile(r"(협찬|제공\s?받|지원\s?받|원고료|소정의|업체로부터|무상으로|광고\s?(포스팅|글)|#광고|\[광고\])")
NEG=re.compile(r"(협찬이?나?\s?체험단이?\s?아닌|협찬\s?아닌|내돈내산|협찬이\s?아닙|협찬\s?없|제공받지)")
SPON=re.compile(r"(reviewnote|revu|dinnerqueen|xn--939au0g4vj8sq|gangnammatzip|4blog|gaboja|assaview|supermembers|ringble|seoulouba|mrblog|tble|cometoplay|chvu|dailyview|reviewplace|storyn|popomon)",re.I)
HOWTO=re.compile(r"(위젯|체험단 사이트|플랫폼|선정|체험단이란|배너|방법)")
def ws(t): return t.replace("\u200b","").strip()
out=[]
for r in R:
    s=BeautifulSoup(open(f'posts/{r["key"]}.html',encoding="utf-8").read(),"html.parser")
    c=s.select_one(".se-main-container")
    comps=c.select(".se-component")
    howto = r["map"]==0 and bool(HOWTO.search(r["title"]))
    lines=[ws(p.get_text()) for p in c.select("p.se-text-paragraph")]; lines=[l for l in lines if l]
    di=[i for i,l in enumerate(lines) if DISC.search(l) and not NEG.search(l)]
    banner=[i for i,d in enumerate(comps) if any(SPON.search(a.get("href","")) for a in d.select("a")) or any(SPON.search(i2.get("src","")) for i2 in d.select("img"))]
    title_disc=bool(re.search(r"협찬|\[광고\]|체험단",r["title"]))
    neg=any(NEG.search(l) for l in lines) or "내돈내산" in r["title"]
    spon = (bool(di) or bool(banner) or title_disc) and not (neg and not banner and not di)
    r.update(howto=howto,spon=spon,naedon=neg and not spon,
             disc_text_pos=(di[0]/len(lines)) if di else None, disc_text=[lines[i] for i in di][:3],
             banner_pos=(banner[0]/len(comps)) if banner else None, title_disc=title_disc)
    out.append(r)
json.dump(out,open("rows2.json","w",encoding="utf-8"),ensure_ascii=False)
P=[r for r in out if not r["howto"]]
S=[r for r in P if r["spon"]]
print("restaurant posts",len(P),"sponsored",len(S),"naedon",sum(r["naedon"] for r in P),"howto excluded",sum(r["howto"] for r in out))
for r in S:
    tp=r["disc_text_pos"]; bp=r["banner_pos"]
    print(f'{r["key"][:24]:24} title={int(r["title_disc"])} text@{"-" if tp is None else round(tp,2)} banner@{"-" if bp is None else round(bp,2)} | {r["title"][:34]} | {" / ".join(x[:60] for x in r["disc_text"][:2])}')
