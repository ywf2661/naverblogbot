import json, os, time, truststore
truststore.inject_into_ssl()
import requests
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36","Accept-Language":"ko-KR,ko;q=0.9","Referer":"https://blog.naver.com/"}
s=json.load(open("search.json",encoding="utf-8"))
seen=set(); n=0
for q,urls in s.items():
    for rank,(bid,log) in enumerate(urls,1):
        key=f"{bid}_{log}"
        if key in seen: continue
        seen.add(key)
        p=f"posts/{key}.html"
        if not os.path.exists(p):
            r=requests.get("https://blog.naver.com/PostView.naver",params={"blogId":bid,"logNo":log,"redirect":"Dlog","widgetTypeCall":"true","directAccess":"false"},headers=H,timeout=20)
            open(p,"w",encoding="utf-8").write(r.text)
            t=requests.get("https://blog.naver.com/BlogTagListInfo.naver",params={"blogId":bid,"logNoList":log,"logType":"mylog"},headers=H,timeout=20)
            open(f"posts/{key}.tags.json","w",encoding="utf-8").write(t.text)
            time.sleep(0.7)
        json.dump({"query":q,"rank":rank},open(f"posts/{key}.meta.json","w",encoding="utf-8"),ensure_ascii=False)
        n+=1
print(n)
