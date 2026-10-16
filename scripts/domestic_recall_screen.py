"""Public Korean recall-list and news-title screening; NOT a recall/press absence audit.

KATRI recall API requires prior agreement, and is not called here.
"""
from __future__ import annotations
import argparse,json,re
from datetime import datetime,timedelta,timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode,urlsplit,urljoin
from urllib.request import Request,urlopen
from urllib.error import URLError,HTTPError
from xml.etree import ElementTree as ET

KST=timezone(timedelta(hours=9))
OFFICIAL="https://www.car.go.kr/ri/stat/list.do"
RSS="https://news.google.com/rss/search"
TARGETS={"26V664000":("G80","제네시스"),"26V588000":("아이오닉9",)}
MAX_BYTES=500_000

class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active=None;self.links=[];self.text=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":self.active={"href":dict(attrs).get("href") or "","text":""}
    def handle_data(self,data):
        self.text.append(data)
        if self.active is not None:self.active["text"]+=data
    def handle_endtag(self,tag):
        if tag=="a" and self.active is not None:
            self.links.append(self.active);self.active=None

def get(url):
    u=urlsplit(url)
    if (u.scheme,u.hostname,u.path) not in (
        ("https","www.car.go.kr","/ri/stat/list.do"),
        ("https","news.google.com","/rss/search")):
        raise ValueError("source_url_not_allowlisted")
    with urlopen(Request(url,headers={
        "User-Agent":"industry-newsroom-public-evidence-screen/1.0",
        "Accept":"text/html,application/rss+xml"}),timeout=12) as response:
        final=urlsplit(response.geturl())
        if (final.scheme,final.hostname,final.path)!=(u.scheme,u.hostname,u.path):
            raise ValueError("unexpected_source_redirect")
        data=response.read(MAX_BYTES+1)
    if not data or len(data)>MAX_BYTES:raise ValueError("invalid_source_size")
    return data

def official_query(term):
    return OFFICIAL+"?"+urlencode({"ctype":"O","currentPageNo":"1","searchProductName":term})

def parse_official(raw,term):
    h=Links();h.feed(raw.decode("utf-8","replace"))
    all_text="".join(h.text)
    if "리콜현황" not in all_text or "국토교통부" not in all_text:
        raise ValueError("unexpected_official_page")
    simple=lambda s:re.sub(r"\s+","",str(s)).upper()
    matches=[]
    for a in h.links[:200]:
        title=" ".join(a["text"].split())
        href=urlsplit(urljoin(OFFICIAL,a["href"]))
        if (simple(term) not in simple(title) or "리콜" not in title
            or href.scheme!="https" or href.hostname!="www.car.go.kr"
            or not href.path.startswith("/ri/")):continue
        if title not in matches:matches.append(title[:160])
        if len(matches)==5:break
    return matches

def news_query(campaign):
    text=('"제네시스" "시트" "리콜" when:45d' if campaign=="26V664000"
          else '"아이오닉9" "리콜" when:45d')
    return RSS+"?"+urlencode({"q":text,"hl":"ko","gl":"KR","ceid":"KR:ko"})

def relevant_news_title(title,campaign):
    """Reject obviously unrelated model headlines; matching still is NOT press verification."""
    compact=re.sub(r"\s+","",title).upper()
    if campaign=="26V664000":
        g80=bool(re.search(r"(?<![A-Z0-9])G80(?![A-Z0-9])",compact))
        genesis_seat="제네시스" in compact and any(
            x in compact for x in ("시트","스위치","리콜","화재","과열"))
        return (g80 or genesis_seat) and any(x in compact
            for x in ("리콜","시트","스위치","화재","과열","RECALL"))
    if campaign=="26V588000":
        return "아이오닉9" in compact and any(
            x in compact for x in ("리콜","시트","RECALL"))
    return False

def parse_news(raw,now,campaign):
    root=ET.fromstring(raw)
    if root.tag!="rss" or root.find("channel") is None:
        raise ValueError("invalid_news_index")
    result=[]
    for item in root.findall("./channel/item")[:30]:
        title=(item.findtext("title") or "").strip()
        link=(item.findtext("link") or "").strip()
        try:stamp=parsedate_to_datetime(item.findtext("pubDate") or "")
        except (ValueError,TypeError):continue
        u=urlsplit(link)
        if (not title or not relevant_news_title(title,campaign) or stamp.utcoffset() is None
            or u.scheme!="https" or u.hostname!="news.google.com"
            or stamp>now+timedelta(minutes=20) or now-stamp>timedelta(days=45)):
            continue
        result.append({"headline":title[:190],"indexUrl":link,
            "publishedAt":stamp.astimezone(KST).isoformat(timespec="minutes"),
            "fulltextRead":False,"sameIssueVerified":False})
        if len(result)==4:break
    return result

def scan(source,*,now=None,fetch=get):
    now=now or datetime.now(KST)
    if now.utcoffset() is None:raise ValueError("timezone_required")
    if (not isinstance(source,dict) or source.get("status")!="official_us_recalls_to_review"
        or source.get("confirmedScoops")!=0
        or not isinstance(source.get("generatedAt"),str)
        or not isinstance(source.get("leads"),list)):
        raise ValueError("source_unverified")
    authorized={x.get("id") for x in source["leads"]
        if isinstance(x,dict) and x.get("usRecallExists") is True
        and x.get("koreanRecallChecked") is False and x.get("exclusiveConfirmed") is False}
    items=[];requests=0
    for campaign,models in TARGETS.items():
        if campaign not in authorized:continue
        queries=[]
        for term in models:
            q={"term":term,"searchUrl":official_query(term),
               "status":"not_checked","visibleModelTitleClues":[],
               "searchFilterVerified":False,"allPagesRead":False,
               "exactPartVerified":False,"recallAbsenceVerified":False}
            try:
                q["visibleModelTitleClues"]=parse_official(fetch(q["searchUrl"]),term)
                q["status"]="public_first_page_only_search_filter_unverified"
            except (ValueError,TypeError,UnicodeError,TimeoutError,URLError,HTTPError,OSError) as exc:
                q["status"]="public_page_unavailable_or_unparsed"
                q["errorType"]=type(exc).__name__
            requests+=1;queries.append(q)
        p={"searchUrl":news_query(campaign),"status":"not_checked","headlines":[],
           "fulltextRead":False,"sameAngleCovered":False,"pressAbsenceVerified":False}
        try:
            p["headlines"]=parse_news(fetch(p["searchUrl"]),now,campaign)
            p["status"]="headline_index_only"
        except (ValueError,TypeError,ET.ParseError,TimeoutError,URLError,HTTPError,OSError) as exc:
            p["status"]="news_index_unavailable_or_unparsed";p["errorType"]=type(exc).__name__
        requests+=1
        items.append({"campaign":campaign,"officialQueries":queries,"press":p,
            "domesticRecallAbsenceVerified":False,"domesticIdenticalPartVerified":False,
            "sameAnglePressFulltextVerified":False,"exclusiveConfirmed":False})
    if requests>5:raise ValueError("request_budget_exceeded")
    return {"generatedAt":now.astimezone(KST).isoformat(timespec="seconds"),
        "sourceUsSnapshot":source["generatedAt"],
        "status":"public_search_screen_not_complete_official_or_press_audit",
        "requestsAttempted":requests,"recallApiAuthorization":"required_not_connected",
        "allKoreanRecallPagesRead":False,"sameAnglePressFulltextChecked":False,
        "confirmedScoops":0,"items":items}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",default="digests/crossborder_safety_latest.json")
    parser.add_argument("--out",default="digests/domestic_recall_screen_latest.json")
    a=parser.parse_args()
    result=scan(json.loads(Path(a.source).read_text(encoding="utf-8")))
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    tmp=dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(dest)
    print("Public recall/news index screening only",result["requestsAttempted"],
          "attempts; no Korean recall absence or exclusive conclusion")

if __name__=="__main__":main()
