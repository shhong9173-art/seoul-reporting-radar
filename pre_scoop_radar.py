from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

KST = timezone(timedelta(hours=9))
OUT = Path("pre_scoop.json")
LOOKBACK_DAYS = 21
SOURCE_DIAGNOSTICS = {}
DIRECT_DIAGNOSTICS = {}

TARGET_COMPANIES = [
    "현대차","기아","제네시스","현대모비스","현대위아","HL만도","한국GM","KG모빌리티",
    "메르세데스벤츠코리아","폭스바겐코리아","BMW코리아","르노코리아","아우디코리아","혼다코리아",
    "한국타이어","넥센타이어","금호타이어","현대트랜시스","현대글로비스",
    "포스코","포스코홀딩스","현대제철","KG스틸","세아홀딩스","세아제강","고려아연","영풍","LS MnM",
    "HD현대일렉트릭","LS일렉트릭","대한전선","효성중공업","일진전기","LS전선","LS지주",
    "두산에너빌리티","GS","GS칼텍스","한화솔루션","OCI","OCI홀딩스","씨에스윈드",
    "태광","동성케미칼","DL케미칼","LG화학","롯데케미칼","금호석유화학","효성첨단소재","코오롱인더",
    "현대오토에버","삼성전기","LG에너지솔루션","삼성SDI","SK온","SK이노베이션",
    "포스코퓨처엠","엘앤에프","포스코인터내셔널"
]
COMPANY_GROUPS = [
    TARGET_COMPANIES[0:10], TARGET_COMPANIES[10:20], TARGET_COMPANIES[20:30],
    TARGET_COMPANIES[30:40], TARGET_COMPANIES[40:50], TARGET_COMPANIES[50:60]
]

SOURCE_SPECS = [
    ("법원·분쟁", "g.scourt.go.kr", "(소송 OR 판결 OR 가처분 OR 손해배상 OR 계약 OR 특허 OR 상표 OR 하도급 OR 구조조정)"),
    ("중앙노동위", "nlrc.go.kr", "(판정 OR 결정 OR 조정 OR 부당노동행위 OR 교섭 OR 쟁의 OR 해고 OR 구조조정 OR 단체협약)"),
    ("고용노동", "moel.go.kr", "(특별감독 OR 근로감독 OR 산업안전 OR 중대재해 OR 행정처분 OR 시정명령 OR 임금체불 OR 직장폐쇄)"),
    ("공장·산업단지", "factoryon.go.kr", "(공장등록 OR 등록변경 OR 신설 OR 증설 OR 업종변경 OR 제조시설 OR 산업단지 OR 입주계약 OR 처분)"),
    ("환경·인허가", "ieps.nier.go.kr", "(통합환경허가 OR 변경허가 OR 허가동향 OR 배출시설 OR 공정변경 OR 증설 OR 사업장)"),
    ("R&D·기술", "ntis.go.kr", "(과제수행기관 OR 연구개발 OR 기술개발 OR 실증 OR 시제품 OR 사업화 OR 신규과제 OR 연구비)"),
    ("자동차·결함", "kotsa.or.kr", "(제작결함 OR 결함조사 OR 자기인증적합조사 OR 리콜 OR 안전기준 OR 인증 OR 배터리)"),
    ("공기업·조달", "kepco.co.kr", "(전자조달 OR 입찰 OR 발주 OR 구매 OR 규격 OR 계약 OR 변압기 OR HVDC OR 케이블 OR 송전 OR 배전)"),
    ("공기업·조달", "khnp.co.kr", "(K-Pro OR 입찰 OR 발주 OR 구매 OR 규격사전공고 OR 계약 OR 원전 OR SMR OR 기자재)"),
    ("공기업·조달", "kepco-enc.com", "(구매규격 OR 사전공개 OR 입찰 OR 계약 OR 원전 OR 플랜트 OR 전력망 OR 기자재)"),
]

SIGNAL_TERMS = re.compile(
    r"공장|증설|신설|생산|가동|생산라인|생산계획|공급중단|공급사|대체투입|재고|납기|인허가|허가|환경영향|변경허가| "
    r"소송|판결|가처분|특허|상표|리콜|결함|조사|행정처분|특별감독|부당노동|교섭|쟁의|파업|구조조정| "
    r"입찰|발주|규격|사전공고|구매|계약|과제|실증|시제품|사업화|연구개발",
    re.I,
)

def get(url, timeout=8):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 NewsroomPreScoop/1.0", "Accept": "application/rss+xml,application/xml,text/xml,*/*"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def clean(s):
    s = html.unescape(s or "")
    s = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", s, flags=re.I | re.S)
    return re.sub(r"\s+", " ", s).strip()

def parse_dt(raw):
    v = str(raw or "").strip()
    if not v:
        return datetime.min.replace(tzinfo=KST)
    normalized = v.replace("년", "-").replace("월", "-").replace("일", "").replace("/", "-").replace(".", "-")
    normalized = re.sub(r"-{2,}", "-", normalized).strip("- ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            d = datetime.strptime(normalized[:19], fmt)
            return d.replace(tzinfo=KST)
        except Exception:
            pass
    try:
        d = parsedate_to_datetime(v)
        return d.astimezone(KST) if d.tzinfo else d.replace(tzinfo=KST)
    except Exception:
        try:
            d = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=KST)
        except Exception:
            return datetime.min.replace(tzinfo=KST)

def target_hits(text):
    t=str(text or "").lower()
    aliases={
        "현대차":["현대차","현대자동차","hyundai motor","[현대]","[hyundai]"],
        "기아":["기아","kia","[기아]"],
        "제네시스":["제네시스","genesis"],
        "현대모비스":["현대모비스","hyundai mobis"],
        "현대위아":["현대위아","hyundai wia"],
        "HL만도":["hl만도","hl mando","만도"],
        "한국GM":["한국gm","gm korea","쉐보레","chevrolet","[쉐보레]"],
        "KG모빌리티":["kg모빌리티","kgm","쌍용자동차"],
        "메르세데스벤츠코리아":["메르세데스벤츠코리아","메르세데스-벤츠 코리아","mercedes-benz korea","벤츠","[벤츠]","[메르세데스-벤츠]"],
        "폭스바겐코리아":["폭스바겐코리아","폭스바겐그룹","volkswagen korea","폭스바겐","[폭스바겐]","[폭스바겐그룹]"],
        "BMW코리아":["bmw코리아","bmw korea","bmw","비엠더블유","[비엠더블유]"],
        "르노코리아":["르노코리아","renault korea","[르노]"],
        "아우디코리아":["아우디코리아","audi korea","아우디"],
        "혼다코리아":["혼다코리아","honda korea","혼다","[혼다]"],
        "한국타이어":["한국타이어","hankook tire"],
        "넥센타이어":["넥센타이어","nexen tire"],
        "금호타이어":["금호타이어","kumho tire"],
        "현대트랜시스":["현대트랜시스","hyundai transys"],
        "현대글로비스":["현대글로비스","hyundai glovis","glovis"],
        "현대오토에버":["현대오토에버","hyundai autoever"],
        "삼성전기":["삼성전기","samsung electro-mechanics","samsung electro mechanics"],
        "LG에너지솔루션":["lg에너지솔루션","lg energy solution","lges"],
        "삼성SDI":["삼성sdi","samsung sdi"],
        "SK온":["sk온","sk on"],
        "SK이노베이션":["sk이노베이션","sk innovation"],
        "포스코퓨처엠":["포스코퓨처엠","posco future m"],
        "엘앤에프":["엘앤에프","l&f","lnf"],
        "포스코인터내셔널":["포스코인터내셔널","posco international"],
        "포스코":["포스코","posco"],
        "포스코홀딩스":["포스코홀딩스","posco holdings"],
        "현대제철":["현대제철","hyundai steel"],
        "KG스틸":["kg스틸","kg steel"],
        "세아홀딩스":["세아홀딩스","seah holdings"],
        "세아제강":["세아제강","seah steel"],
        "고려아연":["고려아연","korea zinc"],
        "영풍":["영풍","young poong"],
        "LS MnM":["ls mnm","ls mnm inc"],
        "HD현대일렉트릭":["hd현대일렉트릭","hd hyundai electric"],
        "LS일렉트릭":["ls일렉트릭","엘에스일렉트릭","ls electric"],
        "대한전선":["대한전선","taihan cable"],
        "효성중공업":["효성중공업","hyosung heavy industries"],
        "일진전기":["일진전기","iljin electric"],
        "LS전선":["ls전선","ls cable"],
        "LS지주":["ls지주","ls corp","ls holdings"],
        "두산에너빌리티":["두산에너빌리티","doosan enerbility"],
        "GS":["gs"],
        "GS칼텍스":["gs칼텍스","gs caltex"],
        "한화솔루션":["한화솔루션","hanwha solutions"],
        "OCI":["oci"],
        "OCI홀딩스":["oci홀딩스","oci holdings"],
        "씨에스윈드":["씨에스윈드","cs wind"],
        "태광":["태광","taekwang"],
        "동성케미칼":["동성케미칼","dongsung chemical"],
        "DL케미칼":["dl케미칼","dl chemical"],
        "LG화학":["lg화학","lg chem"],
        "롯데케미칼":["롯데케미칼","lotte chemical"],
        "금호석유화학":["금호석유화학","kumho petrochemical"],
        "효성첨단소재":["효성첨단소재","hyosung advanced materials"],
        "코오롱인더":["코오롱인더","kolon industries"],
    }
    out=[]
    for k,vals in aliases.items():
        matched=[v for v in vals if v in t]
        if matched: out.append((max(len(v) for v in matched),k))
    # Resolve overlapping names to the most specific tracked issuer first.
    return [k for _,k in sorted(out,reverse=True)]

def parse_feed(root, domain, group, now):
    out=[]
    for item in root.findall("./channel/item"):
        title=(item.findtext("title") or "").strip()
        link=(item.findtext("link") or "").strip()
        pub=item.findtext("pubDate") or ""
        desc=clean(item.findtext("description") or "")
        src=item.find("source")
        source_name=(src.text or "").strip() if src is not None else domain
        if not title or not link: continue
        dt=parse_dt(pub)
        if dt < now-timedelta(days=LOOKBACK_DAYS): continue
        body=title+" "+desc
        companies=target_hits(body)
        if not companies: continue
        if not SIGNAL_TERMS.search(body): continue
        out.append({
            "sourceName":source_name,"officialLabel":domain,"querySite":domain,
            "sourceGroup":group,"title":title,"url":link,"published":dt.isoformat(),
            "summary":desc[:3500],"official":True,"preScoop":True,"companies":companies,
        })
    return out

def parse_bing_html(raw, domain, group, now):
    text_raw=raw.decode("utf-8","ignore")
    out=[]
    for m in re.finditer(r'<li class="b_algo".*?</li>',text_raw,re.S|re.I):
        block=m.group(0)
        lm=re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',block,re.S|re.I)
        if not lm: continue
        link=html.unescape(lm.group(1))
        title=clean(lm.group(2))
        sm=re.search(r'<p[^>]*>(.*?)</p>',block,re.S|re.I)
        desc=clean(sm.group(1) if sm else "")
        body=title+" "+desc
        companies=target_hits(body)
        if not companies or not SIGNAL_TERMS.search(body): continue
        out.append({
            "sourceName":domain,"officialLabel":domain,"querySite":domain,
            "sourceGroup":group,"title":title,"url":link,"published":now.isoformat(),
            "summary":desc[:3500],"official":True,"preScoop":True,"companies":companies,
            "searchIndexed":True,
        })
    return out

def fetch_direct_nlrc(max_items=12):
    """Read the NLRC's recent major judgment list directly, then inspect recent case pages for tracked companies."""
    base="https://nlrc.go.kr"
    list_url=base+"/nlrc/mainCase/mainJudgment/list.do"
    now=datetime.now(KST)
    cutoff=now-timedelta(days=LOOKBACK_DAYS)
    try:
        raw=get(list_url, timeout=15).decode("utf-8","ignore")
    except Exception:
        return []
    out=[]; seen=set()
    rows=re.findall(r"<tr[^>]*>(.*?)</tr>", raw, flags=re.I|re.S)
    for row in rows[:24]:
        dm=re.search(r"(20\d{2}-\d{2}-\d{2})", row)
        lm=re.search(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', row, flags=re.I|re.S)
        if not dm or not lm:
            continue
        try:
            dt=datetime.strptime(dm.group(1),"%Y-%m-%d").replace(tzinfo=KST)
        except ValueError:
            continue
        if dt < cutoff:
            continue
        title=clean(lm.group(2))
        href=urllib.parse.urljoin(base,lm.group(1))
        if not title or href in seen:
            continue
        seen.add(href)
        detail=""
        try:
            detail=clean(get(href, timeout=10).decode("utf-8","ignore"))[:12000]
        except Exception:
            detail=""
        body=title+" "+detail
        companies=target_hits(body)
        if not companies or not SIGNAL_TERMS.search(body):
            continue
        out.append({
            "sourceName":"중앙노동위원회","officialLabel":"중앙노동위","querySite":"nlrc.go.kr",
            "sourceGroup":"중앙노동위","title":title,"url":href,"published":dt.isoformat(),
            "summary":detail[:3500],"official":True,"preScoop":True,"companies":companies,
            "directSource":True
        })
        if len(out)>=max_items:
            break
    return out

def fetch_direct_car_recalls(max_items=20):
    """Search official recall listings by rotating tracked maker/model terms, parsing each list row's own date."""
    base="https://car.go.kr"
    list_path="/ri/stat/list.do"
    now=datetime.now(KST)
    cutoff=now-timedelta(days=LOOKBACK_DAYS)
    query_terms=[
        "현대","코나","아이오닉","기아","쏘렌토","EV3","벤츠","BMW",
        "폭스바겐","ID.4","혼다","CR-V","르노","아르카나","쉐보레","트랙스",
        "KG모빌리티","토레스"
    ]
    batches=[query_terms[i:i+4] for i in range(0,len(query_terms),4)]
    slot=int(now.timestamp()//1800)%len(batches)
    # BMW stays in every batch as a regression fixture for multiple dated notices;
    # the remaining terms rotate so other makers continue to be covered over time.
    active_terms=list(dict.fromkeys(["BMW"]+batches[slot][:3]))
    diag={
        "listFetched":False,"queriesAttempted":0,"queriesSucceeded":0,
        "queryTerms":active_terms,"linksScanned":0,"recallTitles":0,
        "datedRows":0,"recentRows":0,"trackedBrandRows":0,"retained":0,
        "errors":[],"sampleEntries":[]
    }
    DIRECT_DIAGNOSTICS["car-recalls"]=diag
    out=[];seen=set()
    anchor_re=re.compile(r'<a[^>]+href=["\']([^"\']*)["\'][^>]*>(.*?)</a>',re.I|re.S)
    date_re=re.compile(r"20\d{2}\s*[-./]\s*\d{1,2}\s*[-./]\s*\d{1,2}")
    for term in active_terms:
        list_url=base+list_path+"?"+urllib.parse.urlencode({
            "ctype":"O","currentPageNo":"1","searchProductName":term
        })
        diag["queriesAttempted"]+=1
        try:
            raw=get(list_url,timeout=8).decode("utf-8","ignore")
            diag["listFetched"]=True
            diag["queriesSucceeded"]+=1
        except Exception as e:
            if len(diag["errors"])<4:
                diag["errors"].append(f"{term}: {type(e).__name__}: {e}")
            continue
        anchors=list(anchor_re.finditer(raw))
        recall_anchor_idxs=[]
        for ai,am in enumerate(anchors):
            atitle=clean(am.group(2))
            if atitle and re.search(r"(?:관련\s*리콜|제작결함|결함조사|중대리콜)",atitle,re.I) and not re.fullmatch(r"(?:자동차)?리콜(?:정보|현황|제도|센터|알리미)?|결함신고|무상점검\s*[·ㆍ]?\s*수리",atitle,re.I):
                recall_anchor_idxs.append(ai)
        next_recall={idx:(anchors[recall_anchor_idxs[pos+1]].start() if pos+1<len(recall_anchor_idxs) else len(raw)) for pos,idx in enumerate(recall_anchor_idxs)}
        for ai,m in enumerate(anchors):
            href_raw=html.unescape(m.group(1).strip())
            title=clean(m.group(2))
            diag["linksScanned"]+=1
            if ai not in next_recall:
                continue
            diag["recallTitles"]+=1
            key=re.sub(r"[^가-힣A-Za-z0-9]","",title).lower()
            if key in seen:
                continue

            # On this site, date metadata sits in sibling list elements after
            # each title anchor. Read only up to the next recall title anchor to
            # prevent borrowing the adjacent recall's date.
            segment_end=next_recall[ai]
            segment=raw[m.end():segment_end]
            date_hits=list(date_re.finditer(segment))
            if not date_hits:
                if len(diag["sampleEntries"])<8:
                    diag["sampleEntries"].append({"title":title,"query":term,"reason":"no-item-date","rowSample":clean(segment)[:240]})
                continue
            try:
                normalized_date=re.sub(r"\s*[-./]\s*","-",date_hits[0].group(0)).strip()
                dt=datetime.strptime(normalized_date,"%Y-%m-%d").replace(tzinfo=KST)
            except ValueError:
                continue
            row_text=clean(raw[m.start():segment_end])
            diag["datedRows"]+=1
            if dt<cutoff or dt>now+timedelta(hours=6):
                if len(diag["sampleEntries"])<8:
                    diag["sampleEntries"].append({"title":title,"query":term,"date":dt.isoformat(),"reason":"outside-window"})
                continue
            diag["recentRows"]+=1
            companies=target_hits(title)
            if not companies:
                if len(diag["sampleEntries"])<8:
                    diag["sampleEntries"].append({"title":title,"query":term,"date":dt.isoformat(),"reason":"brand-not-tracked"})
                continue
            diag["trackedBrandRows"]+=1
            seen.add(key)
            out.append({
                "sourceName":"자동차리콜센터(국토교통부·자동차안전연구원)",
                "officialLabel":"자동차리콜센터","querySite":"car.go.kr",
                "sourceGroup":"자동차·결함","title":title,"url":list_url,
                "published":dt.isoformat(),"summary":row_text[:2000],
                "official":True,"preScoop":True,"directSource":True,
                "companies":companies,"signalType":"official_recall_notice",
                "dateParseVersion":"sequence-v2","sourceQuery":term
            })
            if len(out)>=max_items:
                break
    diag["retained"]=len(out)
    print(f"direct vehicle recall scout: diagnostics={diag}")
    return out


def fetch_source(group, domain, terms, max_items=25):
    now=datetime.now(KST)
    after=(now-timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    out=[];seen=set()
    diag=SOURCE_DIAGNOSTICS.setdefault(domain,{
        "group":group,"rssQueries":0,"rssRawItems":0,"rssAccepted":0,
        "bingQueries":0,"bingResultBlocks":0,"bingAccepted":0,"errors":[]
    })
    # Spread company coverage across half-hour slots instead of making up to
    # 130 serial web requests in a single refresh. Two adjacent batches are
    # checked per run; six batches rotate across three refresh slots.
    slot=int(now.timestamp()//1800)%len(COMPANY_GROUPS)
    company_batches=[COMPANY_GROUPS[slot],COMPANY_GROUPS[(slot+1)%len(COMPANY_GROUPS)]]

    def add(h):
        key=h.get("url") or h.get("title")
        if key and key not in seen:
            seen.add(key); out.append(h)

    def record_error(kind,e):
        msg=f"{kind}: {type(e).__name__}: {e}"
        if len(diag["errors"])<3 and msg not in diag["errors"]:
            diag["errors"].append(msg)

    # 1) Company-targeted searches.
    for companies in company_batches:
        q=f"site:{domain} ({' OR '.join(companies)}) ({terms}) after:{after}"
        url="https://news.google.com/rss/search?q="+urllib.parse.quote(q)+"&hl=ko&gl=KR&ceid=KR:ko"
        diag["rssQueries"]+=1
        try:
            root=ET.fromstring(get(url))
            raw_items=root.findall("./channel/item")
            diag["rssRawItems"]+=len(raw_items)
            parsed=parse_feed(root,domain,group,now)
            diag["rssAccepted"]+=len(parsed)
            for h in parsed: add(h)
        except Exception as e:
            record_error("Google RSS company query",e)
        if len(out)>=max_items: break

    # 2) Signal-targeted search without a huge company OR.
    if len(out)<max_items:
        q=f"site:{domain} ({terms}) after:{after}"
        url="https://news.google.com/rss/search?q="+urllib.parse.quote(q)+"&hl=ko&gl=KR&ceid=KR:ko"
        diag["rssQueries"]+=1
        try:
            root=ET.fromstring(get(url))
            raw_items=root.findall("./channel/item")
            diag["rssRawItems"]+=len(raw_items)
            parsed=parse_feed(root,domain,group,now)
            diag["rssAccepted"]+=len(parsed)
            for h in parsed: add(h)
        except Exception as e:
            record_error("Google RSS signal query",e)

    # 3) General web search fallback.
    if len(out)<max_items:
        for companies in company_batches:
            q=f"site:{domain} ({' OR '.join(companies)}) ({terms})"
            url="https://www.bing.com/search?q="+urllib.parse.quote(q)+"&setlang=ko-KR"
            diag["bingQueries"]+=1
            try:
                raw=get(url)
                diag["bingResultBlocks"]+=len(re.findall(rb'<li class="b_algo"',raw,re.I))
                parsed=parse_bing_html(raw,domain,group,now)
                diag["bingAccepted"]+=len(parsed)
                for h in parsed: add(h)
            except Exception as e:
                record_error("Bing fallback",e)
            if len(out)>=max_items: break

    diag["uniqueRetained"]=len(out)
    return out[:max_items]

def fetch_direct_kepco_enc(max_items=20):
    """Scrape KEPCO Engineering's public purchase-specification board.
    Retain only material rows with an explicit, recent publication date.
    """
    base = "https://www.kepco-enc.com"
    list_url = base + "/portal/bidInformationList.es?mid=a10608020100&type=std"
    now = datetime.now(KST)
    cutoff = now - timedelta(days=LOOKBACK_DAYS)
    material_re = re.compile(
        r"원전|원자력|원자로|SMR|변압기|HVDC|해저케이블|케이블|송전|배전|터빈|발전기|배관|"
        r"플랜트|전력망|풍력|태양광|ESS|배터리|자동차|타이어|철강|강관|수소|암모니아|압축기|"
        r"제어시스템|계측제어|전기설비|주기기|보조기기|정비|계속운전", re.I
    )
    diag={"listFetched":False,"rowsScanned":0,"materialTitles":0,"detailPagesFetched":0,"datedRows":0,"recentRows":0,"retained":0,"errors":[],"sampleRows":[]}
    DIRECT_DIAGNOSTICS["kepco-enc"] = diag
    try:
        raw = get(list_url, timeout=25).decode("utf-8", "ignore")
        diag["listFetched"]=True
    except Exception as e:
        diag["errors"].append(f"list fetch: {type(e).__name__}: {e}")
        print(f"direct procurement scout: KEPCO-ENC list fetch failed: {type(e).__name__}: {e}")
        return []
    out = []
    seen = set()
    rows = re.findall(r"<tr\b[^>]*>.*?</tr>", raw, flags=re.I | re.S)
    diag["rowsScanned"]=len(rows)
    for row in rows:
        # The purchase-spec board renders 사업명 as plain table-cell text; the
        # clickable anchor can be a sequence number/detail control. Read these separately.
        cell_matches=re.findall(r"<td\b[^>]*>(.*?)</td>",row,flags=re.I|re.S)
        cell_texts=[clean(c) for c in cell_matches]
        title_candidates=[
            t for t in cell_texts
            if len(t)>=18 and material_re.search(t)
            and not re.search(r"추정가격|낙찰자 결정방법|세부사항|바로가기|상세보기|비고",t)
        ]
        link_matches=re.findall(r'<a[^>]+href=["\']([^"\']*)["\'][^>]*>(.*?)</a>',row,flags=re.I|re.S)
        detail_hrefs=[]
        for raw_href,_raw_title in link_matches:
            raw_href=html.unescape(raw_href.strip())
            if not raw_href or raw_href=="#" or raw_href.lower().startswith("javascript:"):
                continue
            detail_hrefs.append(urllib.parse.urljoin(base,raw_href))
        if not title_candidates or not detail_hrefs:
            if len(diag["sampleRows"])<8:
                diag["sampleRows"].append({"row":clean(row)[:350],"cells":cell_texts[:5],"links":[{"href":html.unescape(h),"title":clean(t)} for h,t in link_matches[:4]]})
            continue
        title=max(title_candidates,key=len)
        href=detail_hrefs[0]
        if not title or href in seen:
            continue
        seen.add(href)
        diag["materialTitles"]+=1
        row_text = clean(row)
        date_match = re.search(r"20\d{2}\s*(?:[-./년])\s*\d{1,2}\s*(?:[-./월])\s*\d{1,2}\s*(?:일)?(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?", row_text)
        detail_text = ""
        if not date_match:
            try:
                diag["detailPagesFetched"]+=1
                detail_text = clean(get(href, timeout=8).decode("utf-8", "ignore"))[:16000]
            except Exception as e:
                if len(diag["errors"])<3:
                    diag["errors"].append(f"detail fetch: {type(e).__name__}: {e}")
                detail_text = ""
            date_match = re.search(r"20\d{2}\s*(?:[-./년])\s*\d{1,2}\s*(?:[-./월])\s*\d{1,2}\s*(?:일)?(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?", detail_text)
        if not date_match:
            continue
        diag["datedRows"]+=1
        dt = parse_dt(date_match.group(0))
        if dt.year < 2000 or dt < cutoff or dt > now + timedelta(hours=6):
            continue
        diag["recentRows"]+=1
        body = title + " " + row_text + " " + detail_text
        numbers = re.findall(r"(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:\s*)(?:원|억원|만원|MW|GW|kV|톤|km)", body, re.I)
        out.append({
            "sourceName": "한국전력기술 구매규격 사전공개",
            "officialLabel": "한국전력기술",
            "querySite": "kepco-enc.com",
            "sourceGroup": "공기업·조달",
            "title": title,
            "url": href,
            "published": dt.isoformat(),
            "summary": (row_text + " " + detail_text[:2000])[:3500],
            "official": True,
            "preScoop": True,
            "directSource": True,
            "procurementSignal": True,
            "companies": target_hits(body),
            "numbers": list(dict.fromkeys(numbers))[:5],
        })
        if len(out) >= max_items:
            break
    diag["retained"]=len(out)
    print(f"direct procurement scout: KEPCO-ENC diagnostics={diag}")
    return out

def main():
    items = []
    by_group = {}
    for group, domain, terms in SOURCE_SPECS:
        hits = fetch_source(group, domain, terms)
        items.extend(hits)
        by_group[group] = by_group.get(group, 0) + len(hits)

    direct_nlrc = fetch_direct_nlrc()
    items.extend(direct_nlrc)
    by_group["중앙노동위"] = by_group.get("중앙노동위", 0) + len(direct_nlrc)

    direct_procurement = fetch_direct_kepco_enc()
    items.extend(direct_procurement)
    by_group["공기업·조달"] = by_group.get("공기업·조달", 0) + len(direct_procurement)

    direct_recalls = fetch_direct_car_recalls()
    items.extend(direct_recalls)
    by_group["자동차·결함"] = by_group.get("자동차·결함", 0) + len(direct_recalls)

    # Persist rolling official-source signals across rotating query batches.
    # Old recall records collected by the previous, date-contaminating parser are
    # deliberately discarded unless they carry the current parse-version marker.
    now=datetime.now(KST)
    prior_items=[]
    try:
        previous=json.loads(OUT.read_text(encoding="utf-8"))
        prior_items=previous.get("items",[]) if isinstance(previous,dict) else []
    except Exception:
        prior_items=[]
    for item in prior_items:
        dt=parse_dt(item.get("published"))
        if dt.year<2000 or dt<now-timedelta(days=LOOKBACK_DAYS) or dt>now+timedelta(hours=6):
            continue
        if item.get("signalType")=="official_recall_notice" and item.get("dateParseVersion")!="sequence-v2":
            continue
        items.append(item)

    # Keep the feed compact and deterministic.
    dedup = {}
    for x in items:
        key = (x["sourceGroup"], re.sub(r"[^가-힣A-Za-z0-9]", "", x["title"]).lower())
        dedup[key] = x
    items = sorted(dedup.values(), key=lambda x: x["published"], reverse=True)[:80]
    payload = {
        "generatedAt": datetime.now(KST).isoformat(),
        "lookbackDays": LOOKBACK_DAYS,
        "sourceGroups": by_group,
        "sourceDiagnostics": SOURCE_DIAGNOSTICS,
        "directSourceDiagnostics": DIRECT_DIAGNOSTICS,
        "items": items,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"pre-scoop radar: {sum(by_group.values())} hits / {len(items)} retained / groups={by_group}")

if __name__ == "__main__":
    main()
