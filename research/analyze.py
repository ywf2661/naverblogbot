import json, re, glob, statistics as st, urllib.parse
from collections import Counter
from bs4 import BeautifulSoup
EMOJI=re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\u2B06\u2194-\u21FF\u3030\u303D]")
DISC=re.compile(r"(협찬|제공받|지원받|원고료|소정의|광고|체험단|업체로부터|무상으로|대가)")
SPONSOR_DOM=re.compile(r"(reviewnote|revu|dinnerqueen|xn--939au0g4vj8sq|gangnam|4blog|gaboja|assaview|supermembers|ringble|seoulouba|mrblog|tble|cometoplay|chvu|dailyview|reviewplace|modan|storyn|blogdex|popomon|naver\.me)",re.I)
def ws(t): return t.replace("\u200b","").strip()
rows=[]
for f in glob.glob("posts/*.html"):
    key=f[6:-5]
    s=BeautifulSoup(open(f,encoding="utf-8").read(),"html.parser")
    c=s.select_one(".se-main-container")
    if not c: continue
    meta=json.load(open(f"posts/{key}.meta.json",encoding="utf-8"))
    title=ws(s.select_one(".se-title-text").get_text()) if s.select_one(".se-title-text") else ""
    comps=c.select(":scope > .se-component, .se-component")
    kinds=[]
    for d in c.select(".se-component"):
        k=[x[3:] for x in d.get("class",[]) if x.startswith("se-") and x not in("se-component","se-l-default") and not x.startswith("se-l-") and not x.startswith("se-section")]
        kinds.append(k[0] if k else "?")
    imgs=len(c.select("img.se-image-resource")) or len(c.select(".se-module-image img"))
    ps=c.select("p.se-text-paragraph")
    lines=[ws(p.get_text()) for p in ps]
    nonempty=[l for l in lines if l]
    blanks=len(lines)-len(nonempty)
    # paragraph blocks
    blocks=[];cur=0
    for l in lines:
        if l: cur+=1
        elif cur: blocks.append(cur);cur=0
    if cur: blocks.append(cur)
    align=Counter(next((x.replace("se-text-paragraph-align-","") for x in p.get("class",[]) if "align-" in x),"left") for p in ps if ws(p.get_text()))
    fs=Counter(x for p in ps for sp in p.select("span") for x in sp.get("class",[]) if x.startswith("se-fs-") and x!="se-fs-")
    ff=Counter(x for p in ps for sp in p.select("span") for x in sp.get("class",[]) if x.startswith("se-ff-") and x!="se-ff-")
    lh=Counter(p.get("style") for p in ps if p.get("style"))
    ls=len(re.findall("letter-spacing",str(c)))
    bold=sum(1 for p in ps for b in p.select("b, strong, .se-bold") )
    colored=sum(1 for sp in c.select("span[style*=color]"))
    text="\n".join(nonempty)
    body_nospace=len(re.sub(r"\s","",text))
    hrefs=[a.get("href","") for a in c.select("a")]+[i.get("src","") for i in c.select("img")]
    sponsor_link=any(SPONSOR_DOM.search(h or "") for h in hrefs if "map" not in (h or ""))
    disc_idx=[i for i,l in enumerate(nonempty) if DISC.search(l)]
    disc_pos=None
    if disc_idx: disc_pos=disc_idx[0]/max(1,len(nonempty))
    naedon="내돈내산" in title or "내돈내산" in text
    sponsored=bool(disc_idx) or sponsor_link or bool(re.search(r"협찬|체험단|광고",title))
    try:
        tj=json.loads(open(f"posts/{key}.tags.json",encoding="utf-8").read())
        tags=[t for t in urllib.parse.unquote(tj["taglist"][0]["tagName"]).split(",") if t]
    except Exception: tags=[]
    inline_tags=re.findall(r"#[^\s#]+",text)
    ends=Counter()
    for l in nonempty:
        e=re.sub(EMOJI,"",l).rstrip(" ~!.?ㅎㅋ^")
        if l.endswith(("ㅎㅎ","ㅋㅋ","ㅎ")): ends["ㅎㅎ/ㅋㅋ"]+=1
        if e.endswith("요"): ends["~요"]+=1
        elif e.endswith(("다","니다")): ends["~다"]+=1
        elif e.endswith(("음","함","듯")): ends["~음/함"]+=1
    rest=bool(c.select(".se-placesMap,.se-map")) or bool(re.search(r"맛집|식당|카페|점심|저녁|메뉴",title))
    # image runs and text between images
    runs=[];r=0;textlen_between=[];tl=0
    for d in c.select(".se-component"):
        cl=d.get("class",[])
        if any(x in cl for x in("se-image","se-imageStrip","se-imageGroup")):
            r+=len(d.select("img.se-image-resource")) or 1
            if tl: textlen_between.append(tl);tl=0
        elif "se-text" in cl:
            if r: runs.append(r);r=0
            tl+=sum(1 for p in d.select("p.se-text-paragraph") if ws(p.get_text()))
    if r: runs.append(r)
    heads=[l for l in nonempty if len(l)<=25 and (EMOJI.match(l) or l.startswith(("<","[","▶","■","●","◆","♥","✔","📍","#"," -")))]
    rows.append(dict(key=key,q=meta["query"],rank=meta["rank"],title=title,title_len=len(title),kinds=Counter(kinds),imgs=imgs,
        lines=len(nonempty),blanks=blanks,blocks=blocks,chars=body_nospace,chars_sp=len(text),line_len=[len(l) for l in nonempty],
        align=align,fs=fs,ff=ff,lh=lh,letter_spacing=ls,bold=bold,colored=colored,emoji=len(EMOJI.findall(text)),emojis=Counter(EMOJI.findall(text)),
        tags=tags,inline_tags=inline_tags,ends=ends,sponsored=sponsored,naedon=naedon,disc_pos=disc_pos,disc_line=nonempty[disc_idx[0]] if disc_idx else None,
        sponsor_link=sponsor_link,rest=rest,runs=runs,text_between=textlen_between,heads=heads,first=nonempty[:3],last=nonempty[-4:],
        video=kinds.count("video")+kinds.count("oembed"),map=kinds.count("placesMap")+kinds.count("map"),sticker=kinds.count("sticker"),
        quote=kinds.count("quotation"),hr=kinds.count("horizontalLine"),stitle=kinds.count("sectionTitle")))
json.dump(rows,open("rows.json","w",encoding="utf-8"),ensure_ascii=False,default=lambda o:dict(o))
print(len(rows), sum(r["rest"] for r in rows), sum(r["sponsored"] for r in rows if r["rest"]))
