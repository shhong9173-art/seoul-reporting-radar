"""probe 111: 경쟁지 [단독] 색인 — 구글 뉴스 RSS(지금 쓰는 것)와 네이버 뉴스 API가 최근 4일 출입처 [단독] 제목을 각각 몇 건 잡는지(매체·건수만)."""
import collections, os, re, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import requests
OUT = []
def p(*a):
    OUT.append(" ".join(str(x) for x in a))
KST = timezone(timedelta(hours=9))
now = datetime.now(KST)
begin = (now - timedelta(days=3)).date()
SCOOP = re.compile(r"\[\s*단독\s*\]|<단독>|【단독】")
companies = ["현대차", "기아", "현대모비스", "포스코", "현대제철", "고려아연", "HD현대일렉트릭", "LS일렉트릭", "LS전선", "대한전선", "두산에너빌리티",
             "한화솔루션", "LG화학", "롯데케미칼", "SK이노베이션", "에쓰오일", "금호석유화학", "한국타이어", "KG모빌리티", "GS칼텍스"]
cid, sec = os.environ.get("NAVER_CLIENT_ID", "").strip(), os.environ.get("NAVER_CLIENT_SECRET", "").strip()
def clean(t):
    return re.sub(r"<[^>]+>", "", t or "").replace("&quot;", '"').replace("&amp;", "&").strip()
naver = {}
for c in companies:
    r = requests.get("https://naverapihub.apigw.ntruss.com/search/v1/news", params={"query": f"단독 {c}", "display": 100, "sort": "date"},
                     headers={"X-NCP-APIGW-API-KEY-ID": cid, "X-NCP-APIGW-API-KEY": sec}, timeout=20)
    if r.status_code != 200:
        p("naver", c, "HTTP", r.status_code); continue
    for it in r.json().get("items", []):
        t = clean(it.get("title"))
        try:
            d = parsedate_to_datetime(it.get("pubDate")).astimezone(KST).date()
        except Exception:
            continue
        if d >= begin and SCOOP.search(t) and c.replace("현대차", "현대") in t.replace("현대자동차", "현대"):
            naver[re.sub(r"\s+", "", t)] = (t, urllib.parse.urlsplit(it.get("originallink") or it.get("link")).hostname, str(d))
google = {}
beats = ["현대차 OR 기아 OR KG모빌리티", "현대모비스 OR 한국타이어", "포스코 OR 현대제철 OR 고려아연", "HD현대일렉트릭 OR LS일렉트릭 OR 대한전선 OR LS전선 OR 두산에너빌리티",
         "한화솔루션 OR GS칼텍스", "LG화학 OR 롯데케미칼 OR 금호석유화학 OR 에쓰오일 OR SK이노베이션"]
for q0 in beats:
    q = f"[단독] ({q0}) after:{begin} before:{now.date() + timedelta(days=1)}"
    r = requests.get("https://news.google.com/rss/search?q=" + urllib.parse.quote(q) + "&hl=ko&gl=KR&ceid=KR:ko", timeout=20)
    root = ET.fromstring(r.content)
    for it in root.findall("./channel/item"):
        t = (it.findtext("title") or "").strip()
        src = it.find("source")
        s = (src.text or "") if src is not None else ""
        t2 = re.sub(r"\s+-\s+[^-]+$", "", t)
        if SCOOP.search(t2):
            google[re.sub(r"\s+", "", t2)] = (t2, s)
only_naver = [v for k, v in naver.items() if not any(k[:25] in g or g[:25] in k for g in google)]
p(f"최근 4일 출입처 [단독] 제목: 네이버 {len(naver)} · 구글 {len(google)} · 네이버에만 {len(only_naver)}")
p("네이버에만 매체:", collections.Counter(v[1] for v in only_naver).most_common(15))
for t, h, d in only_naver[:12]:
    p("  N|", d, h, t[:90])
text = "\n".join(OUT)
open("/tmp/probe_out.txt", "w").write(text)
print(text[:600])
