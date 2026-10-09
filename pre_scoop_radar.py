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
    "태광","동성케미칼","DL케미칼","LG화학","롯데케미칼","금호석유화학","효성첨단소재","코오롱인더"
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

def get(url, timeout=15):
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
        "현대차":["현대차","현대자동차","hyundai motor"],
        "기아":["기아","kia"],
        "제네시스":["제네시스","genesis"],
        "현대모비스":["현대모비스","hyundai mobis"],
        "현대위아":["현대위아","hyundai wia"],
        "HL만도":["hl만도","hl mando","만도"],
        "한국GM":["한국gm","gm korea","쉐보레","chevrolet"],
        "KG모빌리티":["kg모빌리티","kgm","쌍용자동차"],
        "메르세데스벤츠코리아":["메르세데스벤츠코리아","메르세데스-벤츠 코리아","mercedes-benz korea","벤츠"],
        "폭스바겐코리아":["폭스바겐코리아","volkswagen korea","폭스바겐"],
        "BMW코리아":["bmw코리아","bmw korea","bmw"],
        "르노코리아":["르노코리아","renault korea"],
        "아우디코리아":["아우디코리아","audi korea","아우디"],
        "혼다코리아":["혼다코리아","honda korea"],
        "한국타이어":["한국타이어","hankook tire"],
        "넥센타이어":["넥센타이어","nexen tire"],
        "금호타이어":["금호타이어","kumho tire"],
        "현대트랜시스":["현대트랜시스","hyundai transys"],
        "현대글로비스":["현대글로비스","hyundai glovis","glovis"],
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
        "LS일렉트릭":["ls일렉트릭","ls electric"],
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
        if any(v in t for v in vals): out.append(k)
    return out

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
    """Read the official Korea vehicle recall list directly, not through news search indexing."""
    base="https://www.car.go.kr"
    list_url=base+"/ri/stat/list.do?menuId=0203010000"
    now=datetime.now(KST)
    cutoff=now-timedelta(days=LOOKBACK_DAYS)
    diag={
        "listFetched":False,"linksScanned":0,"recallTitles":0,"datedRows":0,
        "recentRows":0,"trackedBrandRows":0,"retained":0,"errors":[],
        "sampleEntries":[]
    }
    DIRECT_DIAGNOSTICS["car-recalls"]=diag
    try:
        raw=get(list_url,timeout=25).decode("utf-8","ignore")
        diag["listFetched"]=True
    except Exception as e:
        diag["errors"].append(f"list fetch: {type(e).__name__}: {e}")
        print(f"direct vehicle recall scout: list fetch failed: {type(e).__name__}: {e}")
        return []
    out=[];seen=set()
    # The listing renders a detail link followed by publisher/date metadata in the
    # same compact HTML block. Match only links inside the recall-list route.
    link_re=re.compile(r'<a[^>]+href=["\']([^"\']*)["\'][^>]*>(.*?)</a>',re.I|re.S)
    for m in link_re.finditer(raw):
        href_raw=html.unescape(m.group(1).strip())
        title=clean(m.group(2))
        diag["linksScanned"]+=1
        if not title or not re.search(r"(?:관련\s*리콜|관련\s*무상수리|제작결함|결함조사)",title,re.I):
            continue
        if re.fullmatch(r"(?:자동차)?리콜(?:정보|현황|제도|센터|알리미)?|결함신고|무상점검\s*[·ㆍ]?\s*수리",title,re.I):
            continue
        diag["recallTitles"]+=1
        href=urllib.parse.urljoin(base,href_raw)
        if href in seen:
            continue
        seen.add(href)
        left=max(0,m.start()-1800);right=min(len(raw),m.end()+5000)
        context=raw[left:right]
        date_hits=list(re.finditer(r"20\d{2}\s*[-./]\s*\d{1,2}\s*[-./]\s*\d{1,2}",context))
        if not date_hits:
            if len(diag["sampleEntries"])<6:
                diag["sampleEntries"].append({"title":title,"href":href_raw,"context":clean(context)[:500],"reason":"no-date"})
            continue
        center=m.start()-left
        chosen=min(date_hits,key=lambda x:abs(x.start()-center))
        try:
            normalized_date=re.sub(r"\s*[-./]\s*","-",chosen.group(0)).strip()
            dt=datetime.strptime(normalized_date,"%Y-%m-%d").replace(tzinfo=KST)
        except ValueError:
            continue
        diag["datedRows"]+=1
        if dt<cutoff or dt>now+timedelta(hours=6):
            if len(diag["sampleEntries"])<6:
                diag["sampleEntries"].append({"title":title,"href":href_raw,"date":dt.isoformat(),"reason":"outside-window"})
            continue
        diag["recentRows"]+=1
        companies=target_hits(title)
        if not companies:
            if len(diag["sampleEntries"])<6:
                diag["sampleEntries"].append({"title":title,"href":href_raw,"date":dt.isoformat(),"reason":"brand-not-tracked"})
            continue
        diag["trackedBrandRows"]+=1
        # Some recall detail links are rendered as JavaScript handlers; retain the
        # official listing URL rather than emitting a non-navigable javascript: link.
        detail_url=href if href.startswith(("http://","https://")) else (urllib.parse.urljoin(base,href_raw) if href_raw.startswith("/") else list_url)
        if detail_url.lower().startswith("javascript:"):
            detail_url=list_url
        out.append({
            "sourceName":"자동차리콜센터(국토교통부·자동차안전연구원)",
            "officialLabel":"자동차리콜센터","querySite":"car.go.kr",
            "sourceGroup":"자동차·결함","title":title,"url":detail_url,
            "published":dt.isoformat(),"summary":clean(context)[:2500],
            "official":True,"preScoop":True,"directSource":True,
            "companies":companies,"signalType":"official_recall_notice"
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
    company_batches=COMPANY_GROUPS

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
    diag={"listFetched":False,"rowsScanned":0,"materialTitles":0,"detailPagesFetched":0,"datedRows":0,"recentRows":0,"retained":0,"errors":[]}
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
        link_match = re.search(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', row, flags=re.I | re.S)
        if not link_match:
            continue
        title = clean(link_match.group(2))
        href = urllib.parse.urljoin(base, html.unescape(link_match.group(1)))
        if not title or not material_re.search(title) or href in seen:
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
