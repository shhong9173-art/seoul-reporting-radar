"""Probe 74: 출입처·석유화학정유 외신 검색(구글 뉴스, 운영 수집과 같은 질의·같은 요청 이름)의 매체 이름 분포 —
운영 진단(11-01 18:27): 100줄 중 국내 영문판 60, 허용 외신 목록 밖 38, 7일 지남 2. 공개 기사 목록의 매체 이름·건수만 남긴다."""
import collections
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

FOREIGN_OK = re.compile(r"reuters|bloomberg|nikkei|financial times|\bft\b|wall street journal|\bwsj\b|cnbc|associated press|\bap news\b|economist|fortune|barron|"
                        r"s&p global|platts|fastmarkets|argus|mining\.com|kallanish|metal bulletin|utility dive|power engineering|t&d world|recharge|pv magazine|pv tech|"
                        r"electrek|insideevs|automotive news|automotive world|just auto|just-auto|wardsauto|tire business|tyrepress|rubber|tire technology|"
                        r"energy-storage|energy storage news|chemical & engineering|icis|hydrogen insight|financial post|politico|axios|the information|"
                        r"south china morning post|scmp|caixin|nikkei asia|the japan times|asahi|digitimes|electrive|autocar|carscoops|motor1|the verge|techcrunch|"
                        r"hydrocarbon processing|chemical week|chemweek|oil & gas journal|\bogj\b|energy intelligence|\bopis\b", re.I)
DOMESTIC_EN = re.compile(r"korea herald|korea times|joongang|yonhap|korea economic daily|ked global|businesskorea|business korea|pulse by maeil|maeil|"
                         r"chosun|donga|hankyoreh|aju|seoul economic|the investor|korea bizwire|korea\.net|arirang|kbs|mbc|sbs|kpop|asiae|"
                         r"etnews|thelec|the elec|biz\.chosun|koreatechtoday|koreaittimes|newsis|news1|edaily|businesspost|mk\.co\.kr|hankyung", re.I)
QUERY = '"LG Chem" OR "Lotte Chemical" OR "Kumho Petrochemical" OR "S-Oil" OR "SK Innovation" OR "Hyundai Oilbank"'
KST = timezone(timedelta(hours=9))
url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(QUERY) + "&hl=en-US&gl=US&ceid=US:en"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 AutoIndustryGlobalRadar/1.1", "Accept": "application/rss+xml,application/xml,text/xml,*/*"})
root = ET.fromstring(urllib.request.urlopen(req, timeout=20).read())
cut = datetime.now(KST) - timedelta(hours=168)
c = collections.Counter()
recent = collections.Counter()
for it in root.findall("./channel/item"):
    src = (it.findtext("source") or "").strip()
    kind = "domestic" if DOMESTIC_EN.search(src) else ("ok" if FOREIGN_OK.search(src) else "outlet")
    try:
        new = parsedate_to_datetime(it.findtext("pubDate")).astimezone(KST) >= cut
    except Exception:
        new = False
    c[(kind, src)] += 1
    if new:
        recent[(kind, src)] += 1
out = ["items %d" % sum(c.values())]
for (kind, src), n in c.most_common(60):
    out.append(f"{kind} | {src} | {n} (7일 안 {recent[(kind, src)]})")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:500])
