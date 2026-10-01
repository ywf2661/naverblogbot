import sys, re, json, truststore
truststore.inject_into_ssl()
import requests
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36","Accept-Language":"ko-KR,ko;q=0.9"}
queries=["건대 맛집","성수 맛집","홍대 맛집 내돈내산","강남역 맛집 체험단","망원동 맛집","잠실 맛집 협찬","을지로 맛집","연남동 파스타 맛집","부산 서면 맛집","판교 맛집 점심"]
out={}
for q in queries:
    r=requests.get("https://search.naver.com/search.naver",params={"ssc":"tab.blog.all","query":q},headers=H,timeout=20)
    urls=[]
    for m in re.finditer(r'https?://(?:m\.)?blog\.naver\.com/([A-Za-z0-9_\-]+)/(\d{9,})',r.text):
        u=(m.group(1),m.group(2))
        if u not in urls: urls.append(u)
    out[q]=urls[:10]
    print(q, r.status_code, len(urls))
json.dump(out,open("search.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
