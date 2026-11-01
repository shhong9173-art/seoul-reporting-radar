from __future__ import annotations

import base64
import html
import os
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from html.parser import HTMLParser
from scripts.official_publication_date_guard import resurfaced_historical_original
from scripts.official_source_observation import update_source_states

KST = timezone(timedelta(hours=9))
OUT = Path("pre_scoop.json")
LOOKBACK_DAYS = 21
SOURCE_DIAGNOSTICS = {}
DIRECT_DIAGNOSTICS = {}
# Dates of NTIS announcements already read (url → title key, 공고일). An announcement whose own 공고일 is
# outside the lookback never becomes recent again, so it is not reopened every run (2026-10-28: 5 of 8 detail
# reads per run were old announcements, and their timeouts kept the source 'partial' 60 runs in a row).
DETAIL_DATES = {"ntis": {}}
DETAIL_DATES_MAX = 800
# Bing's fallback repeatedly returned off-domain results across official sources.
# It is opt-in until source-level result quality is independently revalidated.
ENABLE_BING_FALLBACK = os.environ.get("ENABLE_BING_FALLBACK", "").strip() == "1"

TARGET_COMPANIES = [
    "현대차","기아","제네시스","현대모비스","현대위아","HL만도","한국GM","KG모빌리티",
    "메르세데스벤츠코리아","폭스바겐코리아","BMW코리아","르노코리아","아우디코리아","혼다코리아",
    "한국타이어","넥센타이어","금호타이어","현대트랜시스","현대글로비스",
    "포스코","포스코홀딩스","현대제철","KG스틸","세아홀딩스","세아제강","고려아연","영풍","LS MnM",
    "HD현대일렉트릭","LS일렉트릭","대한전선","효성중공업","일진전기","LS전선","LS지주",
    "두산에너빌리티","GS","GS칼텍스","S-OIL","HD현대오일뱅크","한화솔루션","OCI","OCI홀딩스","씨에스윈드",
    "태광","동성케미칼","DL케미칼","LG화학","롯데케미칼","금호석유화학","효성첨단소재","코오롱인더",
    "현대오토에버","삼성전기","LG에너지솔루션","삼성SDI","SK온","SK이노베이션",
    "포스코퓨처엠","엘앤에프","포스코인터내셔널",
    "한국전력공사","한국수력원자력","한국전력기술","전력거래소"
]
COMPANY_GROUPS = [
    TARGET_COMPANIES[0:10], TARGET_COMPANIES[10:20], TARGET_COMPANIES[20:30],
    TARGET_COMPANIES[30:40], TARGET_COMPANIES[40:50], TARGET_COMPANIES[50:]
]

SOURCE_SPECS = [
    ("법원·분쟁", "scourt.go.kr", "(소송 OR 판결 OR 가처분 OR 손해배상 OR 계약 OR 특허 OR 상표 OR 하도급 OR 구조조정)"),
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
    r"입찰|발주|규격|사전공고|구매|계약|과제|실증|시제품|사업화|연구개발|법안|개정안|입법예고|행정예고|고시|"
    r"시행령|시행규칙|본회의 통과|반덤핑|상계관세|관세|탄소배출|배출권|수소발전|전력시장|안전기준|조사개시|판정",
    re.I,
)
COMPANYLESS_POLICY_GROUPS = {"고용노동","환경·인허가","법원·분쟁","중앙노동위"}
COMPANYLESS_POLICY_CONTEXT = re.compile(
    r"자동차|전기차|배터리|타이어|철강|강관|변압기|전력망|전력시장|케이블|풍력|태양광|재생에너지|ess|"
    r"수소|수소발전|원전|원자력|smr|산업안전|산업재해|중대재해|탄소|배출권|관세|반덤핑|상계관세|"
    r"환경영향|배출시설|산업단지|공장|공급망|수출|수입|발전|입찰시장",
    re.I,
)
COMPANYLESS_POLICY_ACTION = re.compile(
    r"법안|개정안|입법예고|행정예고|고시|시행령|시행규칙|본회의 통과|조사개시|판정|시정명령|"
    r"행정처분|반덤핑|상계관세|관세|입찰시장|조달제도|사업계획승인|변경허가|환경영향평가|안전기준|확정",
    re.I,
)

def get(url, timeout=8):
    # Use a normal browser HTML preference for web-search pages while keeping
    # XML endpoints usable through content negotiation.
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def decode_web_bytes(raw):
    """Decode UTF-8 first, then Korean legacy encodings without dropping Hangul."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    candidates=[]
    for encoding in ("cp949","euc-kr"):
        try:
            candidate=raw.decode(encoding,errors="replace")
            hangul=sum(1 for ch in candidate if "\uac00"<=ch<="\ud7a3")
            candidates.append((hangul-candidate.count("\ufffd")*20,candidate))
        except Exception:
            continue
    return max(candidates,key=lambda item:item[0])[1] if candidates else raw.decode("utf-8","replace")

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
        "한국전력공사":["한국전력공사","KEPCO","Korea Electric Power Corporation"],
        "한국수력원자력":["한국수력원자력","한수원","KHNP","Korea Hydro & Nuclear Power"],
        "한국전력기술":["한국전력기술","한전기술","KEPCO E&C","KEPCO Engineering & Construction"],
        "전력거래소":["전력거래소","KPX","Korea Power Exchange"],
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
        "S-OIL":["s-oil","에쓰오일","에쓰-오일"],
        "HD현대오일뱅크":["hd현대오일뱅크","현대오일뱅크","hyundai oilbank"],
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
        matched=[]
        for v in vals:
            a=v.lower()
            if re.fullmatch(r"[a-z0-9 &.-]{2,}",a):
                found=bool(re.search(r"(?<![a-z0-9])"+re.escape(a)+r"(?![a-z0-9])",t))
            else:
                found=a in t
            if found:matched.append(a)
        if matched: out.append((max(len(v) for v in matched),k))
    # Resolve overlapping names to the most specific tracked issuer first.
    return [k for _,k in sorted(out,reverse=True)]

def parse_feed(root, domain, group, now, diag=None):
    out=[]
    def reject(reason,title):
        if diag is None:return
        key="rssReject"+reason
        diag[key]=diag.get(key,0)+1
        samples=diag.setdefault("rssRejectSamples",[])
        if len(samples)<8:
            samples.append({"reason":reason,"title":title[:200]})
    for item in root.findall("./channel/item"):
        title=(item.findtext("title") or "").strip()
        link=(item.findtext("link") or "").strip()
        pub=item.findtext("pubDate") or ""
        desc=clean(item.findtext("description") or "")
        src=item.find("source")
        source_name=(src.text or "").strip() if src is not None else domain
        if not title or not link:
            reject("Invalid",title or "[empty title]")
            continue
        dt=parse_dt(pub)
        if dt.year<2000 or dt < now-timedelta(days=LOOKBACK_DAYS) or dt>now+timedelta(hours=6):
            reject("OutsideWindow",title)
            continue
        if resurfaced_historical_original(title, dt):
            reject("HistoricalOriginalResurfaced",title)
            continue
        body=title+" "+desc
        companies=target_hits(body)
        policy_signal=bool(
            not companies
            and group in COMPANYLESS_POLICY_GROUPS
            and COMPANYLESS_POLICY_CONTEXT.search(body)
            and COMPANYLESS_POLICY_ACTION.search(body)
        )
        if not companies and not policy_signal:
            reject("NoCompany",title)
            continue
        if not SIGNAL_TERMS.search(body):
            reject("NoSignalTerm",title)
            continue
        out.append({
            "sourceName":source_name,"officialLabel":domain,"querySite":domain,
            "sourceGroup":group,"title":title,"url":link,"published":dt.isoformat(),
            "summary":desc[:3500],"official":True,"preScoop":True,"companies":companies,
            "policySignal":policy_signal,
        })
    return out

def unwrap_bing_link(link):
    """Resolve Bing's /ck/a wrapper to its encoded destination URL."""
    link=html.unescape(str(link or "")).strip()
    parsed=urllib.parse.urlparse(link)
    host=(parsed.hostname or "").lower()
    if host not in {"bing.com","www.bing.com","cn.bing.com","global.bing.com"}:
        return link
    query=urllib.parse.parse_qs(parsed.query)
    encoded=(query.get("u") or [""])[0]
    if not encoded:
        return link
    # Bing commonly prefixes a URL-safe Base64 destination with 'a1'.
    payload=encoded[2:] if encoded.startswith("a1") else encoded
    try:
        payload += "="*((-len(payload))%4)
        target=base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8","ignore").strip()
        target=html.unescape(target)
        target_parsed=urllib.parse.urlparse(target)
        if target_parsed.scheme in {"http","https"} and target_parsed.hostname:
            return target
    except Exception:
        pass
    # Do not treat a wrapper as a trusted destination if decoding fails.
    return link


def official_host_matches(url, domain):
    host=urllib.parse.urlparse(url or "").netloc.lower().split(":")[0]
    requested=domain.lower()
    if host==requested or host.endswith("."+requested):
        return True
    # The court search subdomain redirects/indexes pages on the parent court domain.
    if requested=="g.scourt.go.kr" and (host=="scourt.go.kr" or host.endswith(".scourt.go.kr")):
        return True
    return False


def parse_bing_html(raw, domain, group, now, diag=None):
    text_raw=raw.decode("utf-8","ignore")
    out=[]
    block_re=r'<li\b(?=[^>]*class=["\'][^"\']*\bb_algo\b[^"\']*["\'])[^>]*>.*?</li>'
    blocks=list(re.finditer(block_re,text_raw,re.S|re.I))
    if diag is not None:
        diag["bingParsedBlocks"]=diag.get("bingParsedBlocks",0)+len(blocks)
    date_re=re.compile(r'20\d{2}\s*[-./]\s*\d{1,2}\s*[-./]\s*\d{1,2}|\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+20\d{2}\b',re.I)
    def reject(reason,title):
        if diag is None:return
        key="bingReject"+reason
        diag[key]=diag.get(key,0)+1
        samples=diag.setdefault("bingRejectSamples",[])
        if len(samples)<8:samples.append({"reason":reason,"title":title[:200]})
    for m in blocks:
        block=m.group(0)
        lm=re.search(r'<h2\b[^>]*>\s*<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',block,re.S|re.I)
        if not lm:
            reject("Malformed","[missing result link]")
            continue
        raw_link=html.unescape(lm.group(1))
        link=unwrap_bing_link(raw_link)
        title=clean(lm.group(2))
        sm=re.search(r'<p\b[^>]*>(.*?)</p>',block,re.S|re.I)
        desc=clean(sm.group(1) if sm else "")
        if not official_host_matches(link,domain):
            reject("OffDomain",title)
            continue
        # Only dates emitted in a structured date attribute or explicit date
        # metadata are publication dates. Dates embedded in tender titles/snippets
        # may be deadlines, not publication timestamps.
        date_value=""
        meta_date=re.search(r'\bdatetime=["\']([^"\']+)["\']',block,re.I)
        if meta_date:
            date_value=meta_date.group(1).strip()
        if not date_value:
            meta_date=re.search(r'<(?:span|div)\b[^>]*(?:class=["\'][^"\']*(?:news_dt|b_date|publication-date|published-date)[^"\']*["\']|itemprop=["\']datePublished["\'])[^>]*>(.*?)</(?:span|div)>',block,re.I|re.S)
            if meta_date:
                date_value=clean(meta_date.group(1))
        date_match=date_re.search(date_value)
        # Search-index retrieval time is not the publication date. Undated results
        # are logged but cannot become fresh leads by borrowing the current time.
        if not date_match:
            reject("Undated",title)
            continue
        dt=parse_dt(date_match.group(0))
        if dt.year<2000 or dt<now-timedelta(days=LOOKBACK_DAYS) or dt>now+timedelta(hours=6):
            reject("OutsideWindow",title)
            continue
        body=title+" "+desc
        companies=target_hits(body)
        if not companies:
            reject("NoCompany",title)
            continue
        if not SIGNAL_TERMS.search(body):
            reject("NoSignalTerm",title)
            continue
        out.append({
            "sourceName":domain,"officialLabel":domain,"querySite":domain,
            "sourceGroup":group,"title":title,"url":link,"published":dt.isoformat(),
            "summary":desc[:3500],"official":True,"preScoop":True,"companies":companies,
            "searchIndexed":True,"dateSource":"indexed-result-snippet",
        })
    return out

def _ntis_detail_url(href):
    """Canonicalize only observed official announcement IDs, never arbitrary hosts."""
    parsed = urllib.parse.urlsplit(urllib.parse.urljoin("https://www.ntis.go.kr", html.unescape(href)))
    if (parsed.scheme not in ("http", "https") or parsed.netloc.lower() != "www.ntis.go.kr"
            or parsed.path != "/rndgate/eg/un/ra/view.do"):
        return ""
    ids = urllib.parse.parse_qs(parsed.query).get("roRndUid", [])
    if len(ids) != 1 or not re.fullmatch(r"\d{1,16}", ids[0]):
        return ""
    return "https://www.ntis.go.kr/rndgate/eg/un/ra/view.do?" + urllib.parse.urlencode({"roRndUid": ids[0]})


NTIS_RETRY_TIMEOUT = 25
NTIS_LATE_RETRIES = 2
NTIS_LATE_PAUSE = 3


def _ntis_fetch(url, diag, stage, timeout=12):
    # NTIS 본문은 실행마다 8건 중 1~3건이 12초 안에 안 온다(10-23~10-28 운영, 매번 다른 쪽 → 사이트 지연).
    # 다시 받을 때는 기다리는 시간을 늘린다. 시도 횟수(2회)와 연속 실패 차단(DETAIL_BREAKER)은 그대로.
    for attempt in range(2):
        diag["httpAttempts"] += 1
        try:
            return decode_web_bytes(get(url, timeout=timeout if attempt == 0 else max(timeout, NTIS_RETRY_TIMEOUT)))
        except (OSError, urllib.error.URLError) as exc:
            retry = attempt == 0 and (not isinstance(exc, urllib.error.HTTPError)
                                     or exc.code == 429 or exc.code >= 500)
            diag["errors"].append({"stage": stage, "url": url, "attempt": attempt + 1,
                                   "error": f"{type(exc).__name__}: {exc}"[:240], "retry": retry})
            if not retry:
                return None
            diag["retries"] += 1
    return None


class _NtisBodyParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div" and (self.depth or "notice_cont" in attrs.get("class", "").split()):
            self.depth += 1
        if self.depth and tag in ("script", "style"):
            self.skip += 1
        if self.depth and tag in ("p", "br", "div", "tr", "li"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.depth and tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        if self.depth and tag in ("p", "div", "tr", "li"):
            self.parts.append("\n")
        if self.depth and tag == "div":
            self.depth -= 1

    def handle_data(self, data):
        if self.depth and not self.skip:
            self.parts.append(data)


def _ntis_title_key(value):
    # NTIS search indexing drops the ampersand in R&D; detail HTML preserves it. '\b' does not separate 'D' from a
    # following Hangul letter ('R&D사업'), so ASCII-only lookarounds are used. The list also writes straight quotes
    # where the detail has curly ones ('한국-헝가리 …' vs ‘한국-헝가리 …’) — quote marks are not compared.
    # (10-30 탐침: 3번 연속 'list_detail_title_mismatch'로 일부 수집 표시된 두 공고)
    v = re.sub(r"(?<![A-Za-z])R\s*&\s*D(?![A-Za-z])", "RD", value or "", flags=re.I)
    v = re.sub(r"[\"'‘’“”`´]", "", v)
    return re.sub(r"\s+", "", v)


def parse_ntis_detail(markup):
    heading = re.search(r'<h1\b[^>]*class=["\'][^"\']*\bditail_tit\b[^"\']*["\'][^>]*>(.*?)</h1>', markup, re.I | re.S)
    if not heading:
        return "", {}, ""
    title = clean(heading[1])
    fields = {}
    for row in re.findall(r"<li\b[^>]*>(.*?)</li>", markup[heading.end():], re.I | re.S):
        match = re.search(r"<span\b[^>]*>(.*?)</span>(.*)", row, re.I | re.S)
        if match:
            label = clean(match[1]).rstrip(":： ")
            if label in ("공고일", "접수일", "마감일", "사업명", "부처명", "공고기관명", "공고금액"):
                fields.setdefault(label, clean(match[2]))
    parser = _NtisBodyParser()
    parser.feed(markup)
    lines = [re.sub(r"\s+", " ", line).strip() for line in "".join(parser.parts).splitlines()]
    return title, fields, "\n".join(line for line in lines if line)


def fetch_direct_ntis_announcements(max_items=12, query_terms=None, max_details=8, prior_items=None, known_dates=None):
    """Bounded official-source collection; round-robin prevents first-term starvation."""
    now = datetime.now(KST)
    cutoff = now - timedelta(days=LOOKBACK_DAYS)
    terms = ["자동차", "전기차", "배터리", "철강", "변압기", "전력망", "해상풍력", "수소발전", "원전", "탄소", "소재"]
    batches = [terms[i:i+3] for i in range(0, len(terms), 3)]
    active_terms = list(dict.fromkeys(query_terms if query_terms is not None else batches[int(now.timestamp() // 1800) % len(batches)]))
    diag = {"queriesAttempted": 0, "searchPagesFetched": 0, "searchPagesParsed": 0,
            "announcementLinks": 0, "invalidLinks": 0, "duplicateLinks": 0,
            "detailPagesAttempted": 0, "detailPagesFetched": 0, "datedRecords": 0,
            "recentRecords": 0, "retained": 0, "httpAttempts": 0, "retries": 0,
            "queryTerms": active_terms, "queryDiagnostics": [], "errors": [],
            "detailReused": 0, "detailDeferred": 0, "detailCircuitOpen": False, "knownOldSkipped": 0,
            "exclusions": {}, "sampleRows": [], "coverageLimited": False}
    DIRECT_DIAGNOSTICS["ntis-announcements"] = diag
    if max_items < 1 or max_details < 1 or not active_terms:
        diag["status"] = "disabled_by_limit"
        return []

    def exclude(reason, url):
        diag["exclusions"][reason] = diag["exclusions"].get(reason, 0) + 1
        if len(diag["sampleRows"]) < 12:
            diag["sampleRows"].append({"url": url, "reason": reason})

    queues = []
    for term in active_terms:
        qdiag = {"term": term, "links": 0, "detailPagesAttempted": 0, "detailPagesFetched": 0}
        diag["queryDiagnostics"].append(qdiag)
        queue = []
        queues.append((qdiag, queue))
        url = "https://www.ntis.go.kr/ThSearchResultAnnouncementList.do?" + urllib.parse.urlencode({
            "searchSentence": "", "searchWord": term, "sort": "SS01/DESC,RANK/DESC"})
        diag["queriesAttempted"] += 1
        markup = _ntis_fetch(url, diag, f"search:{term}")
        if markup is None:
            qdiag["status"] = "search_fetch_failed"
            diag["coverageLimited"] = True
            continue
        diag["searchPagesFetched"] += 1
        for match in re.finditer(r'<a\b[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', markup, re.I | re.S):
            href, title = html.unescape(match[1]), clean(match[2])
            if "/rndgate/eg/un/ra/view.do" not in href:
                continue
            detail_url = _ntis_detail_url(href)
            if not detail_url or len(title) < 10:
                diag["invalidLinks"] += 1
                continue
            queue.append((detail_url, title))
        total = re.search(r'id=["\']totalCnt["\'][^>]*value=["\'](\d+)["\']', markup, re.I)
        if not queue and (not total or int(total[1]) != 0):
            qdiag["status"] = "detail_links_missing_or_invalid_list"
            diag["coverageLimited"] = True
            continue
        diag["searchPagesParsed"] += 1
        qdiag.update(status="list_parsed", links=len(queue), totalResults=int(total[1]) if total else None)
        # Only the first results page is checked, not the whole NTIS catalogue.
        if not total or int(total[1]) > len(queue):
            diag["coverageLimited"] = True

    ordered, seen = [], set()
    for index in range(max((len(queue) for _, queue in queues), default=0)):
        for qdiag, queue in queues:
            if index >= len(queue):
                continue
            url, title = queue[index]
            if url in seen:
                diag["duplicateLinks"] += 1
                continue
            seen.add(url)
            ordered.append((qdiag, url, title))
    diag["announcementLinks"] = len(ordered)
    # A detail read in an earlier run (same official id, same listed title) is reused, not re-read.
    cache = {it.get("url"): it for it in (prior_items or [])
             if isinstance(it, dict) and it.get("signalType") == "ntis_rnd_announcement" and it.get("url")}
    known = {k: v for k, v in (known_dates or {}).items() if isinstance(v, dict)}
    DETAIL_DATES["ntis"] = known
    out, fresh = [], []
    for qdiag, url, listed_title in ordered:
        seen_before = known.get(url)
        if (seen_before and seen_before.get("t") == _ntis_title_key(listed_title)
                and re.fullmatch(r"20\d{2}-\d{2}-\d{2}", str(seen_before.get("d", "")))
                and parse_dt(seen_before["d"]) < cutoff):
            diag["knownOldSkipped"] += 1
            exclude("outside_lookback", url)
            continue
        hit = cache.get(url)
        if hit and _ntis_title_key(hit.get("title")) == _ntis_title_key(listed_title):
            published = parse_dt(hit.get("published"))
            if cutoff <= published <= now + timedelta(hours=6):
                diag["detailReused"] += 1
                diag["datedRecords"] += 1
                diag["recentRecords"] += 1
                out.append(dict(hit))
            continue
        fresh.append((qdiag, url, listed_title))
    ordered = fresh
    def handle(qdiag, url, listed_title, markup):
        diag["detailPagesFetched"] += 1
        qdiag["detailPagesFetched"] += 1
        title, fields, body = parse_ntis_detail(markup)
        if not title:
            exclude("detail_structure_or_title_missing", url)
            return
        if _ntis_title_key(title) != _ntis_title_key(listed_title):
            exclude("list_detail_title_mismatch", url)
            return
        date = re.sub(r"\s+", "", fields.get("공고일", ""))
        dt = parse_dt(date)
        if not re.fullmatch(r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}", date) or dt.year < 2000:
            exclude("announcement_date_missing_or_invalid", url)
            return
        diag["datedRecords"] += 1
        known.pop(url, None)
        known[url] = {"t": _ntis_title_key(title), "d": dt.date().isoformat()}
        while len(known) > DETAIL_DATES_MAX:
            known.pop(next(iter(known)))
        if dt < cutoff or dt > now + timedelta(hours=6):
            exclude("outside_lookback", url)
            return
        diag["recentRecords"] += 1
        if not body or body == "공고내용":
            exclude("body_missing", url)
            return
        out.append({"sourceName": "NTIS 국가R&D통합공고", "officialLabel": "NTIS",
                    "querySite": "ntis.go.kr", "sourceGroup": "R&D·기술", "title": title,
                    "url": url, "published": dt.isoformat(), "summary": body[:3500], "bodyText": body,
                    "official": True, "preScoop": True, "directSource": True, "policySignal": True,
                    "category": "정책·규제", "companies": target_hits(title),
                    "signalType": "ntis_rnd_announcement", "dateSource": "NTIS 공고일",
                    "announcementFields": fields, "programName": fields.get("사업명", ""),
                    "verification": "공개 원자료 추적 — 기업 참여·선정 및 단독 여부 미확인",
                    "evidenceLimitations": ["첨부문서는 수집하지 않음", "공모 자체는 기업 참여의 증거가 아님"]})

    failures_in_row = 0
    failed = []
    for index, (qdiag, url, listed_title) in enumerate(ordered[:max_details]):
        if len(out) >= max_items:
            break
        if failures_in_row >= DETAIL_BREAKER:
            diag["detailCircuitOpen"] = True
            for _, later, _ in ordered[index:max_details]:
                exclude("detail_deferred_after_timeouts", later)
                diag["detailDeferred"] += 1
            break
        if diag["detailPagesAttempted"]:
            time.sleep(DETAIL_GAP_SECONDS)
        diag["detailPagesAttempted"] += 1
        qdiag["detailPagesAttempted"] += 1
        markup = _ntis_fetch(url, diag, "detail")
        if markup is None:
            failures_in_row += 1
            failed.append((qdiag, url, listed_title))
            continue
        failures_in_row = 0
        handle(qdiag, url, listed_title, markup)
    # 두 번 다 끊긴 본문은 다른 본문을 다 읽은 뒤 한 번 더(최대 NTIS_LATE_RETRIES건, 차단이 열리면 안 함).
    # 운영 10-28 22:04·22:13: 1차 끊김 7건 중 6건이 바로 다시 받기로 살아남 — 시간 간격을 두면 대부분 받힌다.
    late = [] if diag["detailCircuitOpen"] else failed[:NTIS_LATE_RETRIES]
    for qdiag, url, listed_title in failed:
        markup = None
        if (qdiag, url, listed_title) in late and len(out) < max_items:
            time.sleep(NTIS_LATE_PAUSE)
            diag["httpAttempts"] += 1
            diag["lateRetries"] = diag.get("lateRetries", 0) + 1
            try:
                markup = decode_web_bytes(get(url, timeout=NTIS_RETRY_TIMEOUT))
            except (OSError, urllib.error.URLError) as exc:
                diag["errors"].append({"stage": "detail-late", "url": url, "attempt": 3,
                                       "error": f"{type(exc).__name__}: {exc}"[:240], "retry": False})
        if markup is None:
            exclude("detail_fetch_failed", url)
            continue
        diag["lateRetryOk"] = diag.get("lateRetryOk", 0) + 1
        # 앞선 두 번의 실패는 '다시 받아 회복'으로 바꿔 적는다(기록은 남긴다).
        for e in diag["errors"]:
            if e.get("url") == url and e.get("stage") == "detail" and e.get("retry") is False:
                e["retry"] = True
                e["recoveredLater"] = True
        handle(qdiag, url, listed_title, markup)
    diag["retained"] = len(out)
    diag["detailsSkippedByLimit"] = max(0, len(ordered) - diag["detailPagesAttempted"] - diag["detailDeferred"])
    diag["coverageLimited"] |= bool(diag["detailsSkippedByLimit"])
    diag["status"] = ("search_fetch_or_parse_failed" if not diag["searchPagesParsed"] else
                      "empty_official_search" if not ordered else
                      "detail_fetch_failed" if not diag["detailPagesFetched"] and not diag["detailReused"] else
                      "detail_parse_failed" if not diag["datedRecords"] else
                      "no_recent_publications_in_checked_details" if not diag["recentRecords"] else
                      "recent_announcements_checked")
    final_errors = [e for e in diag["errors"] if not (isinstance(e, dict) and e.get("retry") is True)]
    diag["collectionComplete"] = not (diag["coverageLimited"] or final_errors or diag["invalidLinks"]
        or any(reason != "outside_lookback" for reason in diag["exclusions"]))
    print(f"direct NTIS announcement scout: diagnostics={diag}")
    return out



IRIS_BASE = "https://www.iris.go.kr"
# 2026-10 운영: 상세 30건 중 21건 시간초과가 58회 연속. 같은 공고를 매번 다시 읽고(재사용 없음),
# 실패가 이어져도 끝까지 시도해 실행마다 수 분씩 기다렸다. 이미 읽은 공고는 재사용하고,
# 목록의 날짜·제목으로 걸러지는 공고는 상세를 열지 않으며, 연속 실패 3번이면 나머지는 다음 실행으로 미룬다.
DETAIL_GAP_SECONDS = 0.6
DETAIL_BREAKER = 3
IRIS_LIST_PATH = "/contents/retrieveBsnsAncmBtinSituList.do"


def _iris_request(url, data=None, timeout=12):
    """Official read-only form POST used by bsnsAncmBtinSituList.js."""
    if data is None:
        return get(url, timeout=timeout)
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), headers={
        "User-Agent": "Mozilla/5.0", "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": IRIS_BASE + "/contents/retrieveBsnsAncmBtinSituListView.do",
    })
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def _iris_fetch(url, data, diag, stage):
    # One retry for transport errors only; parser failures must remain visible.
    for attempt in range(2):
        try:
            return decode_web_bytes(_iris_request(url, data))
        except (OSError, urllib.error.URLError) as exc:
            retry = attempt == 0 and (not isinstance(exc, urllib.error.HTTPError)
                                     or exc.code == 429 or exc.code >= 500)
            diag["errors"].append({"stage": stage, "attempt": attempt + 1,
                                   "error": f"{type(exc).__name__}: {exc}"[:240],
                                   "retry": retry})
            if not retry:
                return None
            diag["retries"] += 1
    return None


class _IrisBodyParser(HTMLParser):
    """Read only the announcement body, excluding menus, scripts and footer."""
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div":
            if self.depth or "tb_contents" in attrs.get("class", "").split():
                self.depth += 1
        if self.depth and tag in ("script", "style"):
            self.skip += 1
        if self.depth and tag in ("p", "br", "tr", "li", "div"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.depth and tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        if self.depth and tag in ("p", "tr", "li", "div"):
            self.parts.append("\n")
        if self.depth and tag == "div":
            self.depth -= 1

    def handle_data(self, data):
        if self.depth and not self.skip:
            self.parts.append(data)


def parse_iris_detail(markup):
    # The real page puts 공고일자 BEFORE 공고명. Match labelled fields, not order.
    fields = {}
    for row in re.findall(r"<li\b[^>]*>(.*?)</li>", markup, re.I | re.S):
        match = re.search(r"<(em|strong)\b[^>]*>(.*?)</\1>\s*<span\b[^>]*>(.*?)</span>",
                          row, re.I | re.S)
        if match:
            fields[clean(match[2])] = clean(match[3])
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", markup, re.I | re.S):
        cells = [clean(cell) for cell in re.findall(r"<(?:td|th)\b[^>]*>(.*?)</(?:td|th)>", row, re.I | re.S)]
        if len(cells) >= 2 and cells[0] in ("지원대상", "지원 대상", "자격조건", "세부사업명", "내역사업명"):
            fields.setdefault(cells[0], " | ".join(cells[1:]))
    parser = _IrisBodyParser()
    parser.feed(markup)
    lines = [re.sub(r"\s+", " ", line).strip() for line in "".join(parser.parts).splitlines()]
    body = "\n".join(line for line in lines if line)
    return fields, body


def _iris_company_mentions(text):
    # These are literal mentions, NOT proof of participation or direct-beat status.
    aliases = {"현대차": ("현대차", "현대자동차"),
               "메르세데스벤츠코리아": ("메르세데스벤츠코리아", "메르세데스-벤츠 코리아"),
               "BMW코리아": ("BMW코리아", "BMW 코리아"),
               "LS MnM": ("LS MnM", "LS M&M")}
    return [name for name in TARGET_COMPANIES if any(
        re.search(r"(?<![\w])" + re.escape(alias) + r"(?![\w])", text, re.I)
        for alias in aliases.get(name, (name,)))]


def fetch_direct_iris_announcements(max_items=10, max_pages=2, max_details=30, prior_items=None):
    """Read official JSON lists and labelled detail HTML; never infer newness.

    Both open and closed calls are checked. Limits are reported as incomplete
    coverage, not evidence that no recent calls exist. No output files are written.
    """
    now = datetime.now(KST)
    cutoff = now - timedelta(days=LOOKBACK_DAYS)
    diag = {"listFetched": False, "listPagesAttempted": 0, "listPagesFetched": 0,
            "listPagesParsed": 0, "detailIdsSeen": 0, "duplicateIds": 0,
            "invalidIds": 0, "detailPagesAttempted": 0, "detailPagesFetched": 0,
            "datedRecords": 0, "recentRecords": 0, "materialRecords": 0,
            "companyMentionRecords": 0, "retained": 0, "retries": 0,
            "detailReused": 0, "listPrefiltered": 0, "detailDeferred": 0, "detailCircuitOpen": False,
            "exclusions": {}, "errors": [], "sampleRows": [], "tabs": {},
            "listUsesJsOrAjax": True, "listTransport": "official_form_post_json",
            "coverageLimited": False}
    DIRECT_DIAGNOSTICS["iris-rnd-announcements"] = diag
    if min(max_items, max_pages, max_details) < 1:
        diag["status"] = "disabled_by_limit"
        return []

    def exclude(reason, ann_id):
        diag["exclusions"][reason] = diag["exclusions"].get(reason, 0) + 1
        if len(diag["sampleRows"]) < 12:
            diag["sampleRows"].append({"ancmId": ann_id, "reason": reason})

    announcements = {}
    for tab in ("ancmIng", "ancmEnd"):
        for page in range(1, max_pages + 1):
            diag["listPagesAttempted"] += 1
            listing = _iris_fetch(IRIS_BASE + IRIS_LIST_PATH,
                                  {"pageIndex": page, "prgmId": "", "ancmPrg": tab},
                                  diag, f"list:{tab}:{page}")
            if listing is None:
                diag["coverageLimited"] = True
                break
            diag["listFetched"] = True
            diag["listPagesFetched"] += 1
            try:
                data = json.loads(listing)
                records = data["listBsnsAncmBtinSitu"]
                paging = data["paginationInfo"]
                total_pages = int(paging["totalPageCount"])
                total_records = int(paging["totalRecordCount"])
                if (not isinstance(records, list) or not all(isinstance(r, dict) for r in records)
                        or int(paging["currentPageNo"]) != page or total_pages < 0 or total_records < 0):
                    raise ValueError("unexpected IRIS list schema/page")
                if not records and total_records > 0:
                    raise ValueError("empty page with nonzero totalRecordCount")
            except (ValueError, KeyError, TypeError) as exc:
                diag["errors"].append({"stage": f"list_parse:{tab}:{page}", "error": str(exc)[:240]})
                diag["coverageLimited"] = True
                break
            diag["listPagesParsed"] += 1
            diag["tabs"][tab] = {"pagesChecked": page, "totalPages": total_pages,
                                  "totalRecords": total_records}
            for record in records:
                ann_id = record.get("ancmId")
                if not isinstance(ann_id, str) or not re.fullmatch(r"\d{4,12}", ann_id):
                    diag["invalidIds"] += 1
                    continue
                if ann_id in announcements:
                    diag["duplicateIds"] += 1
                    continue
                announcements[ann_id] = (tab, record)
            if page >= total_pages:
                break
            if page == max_pages:
                diag["coverageLimited"] = True

    diag["detailIdsSeen"] = len(announcements)
    # Prioritize actual list announcement dates, never application deadlines.
    ordered = sorted(announcements.items(), key=lambda pair: parse_dt(pair[1][1].get("ancmDe")), reverse=True)
    material_re = re.compile(r"자동차|모빌리티|전기차|배터리|이차전지|철강|강관|소재|부품|장비|변압기|전력망|케이블|풍력|태양광|재생에너지|에너지|전력|수소|원전|원자력|SMR|탄소|희소금속|비철|화학|산업기술|제조|실증", re.I)
    # Earlier verified rows (same id, same listed title and date) are reused instead of re-reading the page.
    cache = {it.get("announcementId"): it for it in (prior_items or [])
             if isinstance(it, dict) and it.get("signalType") == "iris_rnd_announcement" and it.get("announcementId")}
    out, to_fetch = [], []
    for ann_id, (tab, listed) in ordered:
        listed_title = clean(listed.get("ancmTl") or "")
        listed_dt = parse_dt(listed["ancmDe"]) if listed.get("ancmDe") else None
        # The list date only decides what NOT to open; the published date always comes from the detail page.
        if listed_dt and listed_dt.year >= 2000 and listed_dt < cutoff - timedelta(days=1):
            exclude("outside_lookback", ann_id)
            diag["listPrefiltered"] += 1
            continue
        if listed_title and not _iris_company_mentions(listed_title) and not material_re.search(listed_title):
            exclude("no_company_or_industry_in_title", ann_id)
            diag["listPrefiltered"] += 1
            continue
        hit = cache.get(ann_id)
        if (hit and listed_title and hit.get("title") == listed_title and listed_dt
                and str(hit.get("published", ""))[:10] == listed_dt.date().isoformat()):
            diag["detailReused"] += 1
            diag["datedRecords"] += 1
            diag["recentRecords"] += 1
            diag["materialRecords"] += 1
            if hit.get("mentionedCompanies"):
                diag["companyMentionRecords"] += 1
            out.append(dict(hit))
            continue
        to_fetch.append((ann_id, tab, listed))
    diag["detailCandidates"] = len(to_fetch) + diag["detailReused"]
    if len(to_fetch) > max_details:
        diag["coverageLimited"] = True
    diag["detailsSkippedByLimit"] = max(0, len(to_fetch) - max_details)
    failures_in_row = 0
    for index, (ann_id, tab, listed) in enumerate(to_fetch[:max_details]):
        if failures_in_row >= DETAIL_BREAKER:
            diag["detailCircuitOpen"] = True
            for later_id, _, _ in to_fetch[index:max_details]:
                exclude("detail_deferred_after_timeouts", later_id)
                diag["detailDeferred"] += 1
            break
        url = IRIS_BASE + "/contents/retrieveBsnsAncmView.do?" + urllib.parse.urlencode({"ancmId": ann_id, "ancmPrg": tab})
        if diag["detailPagesAttempted"]:
            time.sleep(DETAIL_GAP_SECONDS)
        diag["detailPagesAttempted"] += 1
        markup = _iris_fetch(url, None, diag, f"detail:{ann_id}")
        if markup is None:
            failures_in_row += 1
            exclude("detail_fetch_failed", ann_id)
            continue
        failures_in_row = 0
        diag["detailPagesFetched"] += 1
        fields, body = parse_iris_detail(markup)
        title = fields.get("공고명", "")
        if not title:
            exclude("detail_structure_or_title_missing", ann_id)
            continue
        date = re.sub(r"\s+", "", fields.get("공고일자", ""))
        if not re.fullmatch(r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}", date) or parse_dt(date).year < 2000:
            exclude("announcement_date_missing_or_invalid", ann_id)
            continue
        dt = parse_dt(date)
        diag["datedRecords"] += 1
        if listed.get("ancmDe") and parse_dt(listed["ancmDe"]).date() != dt.date():
            exclude("list_detail_date_mismatch", ann_id)
            continue
        if listed.get("ancmTl") and clean(listed["ancmTl"]) != title:
            exclude("list_detail_title_mismatch", ann_id)
            continue
        if dt < cutoff or dt > now + timedelta(hours=6):
            exclude("outside_lookback", ann_id)
            continue
        diag["recentRecords"] += 1
        if not body:
            exclude("body_missing", ann_id)
            continue
        companies = _iris_company_mentions(title)
        mentions = _iris_company_mentions(title + " " + body)
        if mentions:
            diag["companyMentionRecords"] += 1
        if not companies and not material_re.search(title):
            exclude("no_company_or_industry_in_title", ann_id)
            continue
        diag["materialRecords"] += 1
        out.append({
            "sourceName": "범부처통합연구지원시스템 사업공고", "officialLabel": "IRIS",
            "querySite": "iris.go.kr", "sourceGroup": "R&D·기술", "title": title,
            "url": url, "published": dt.isoformat(), "summary": body[:3500],
            "official": True, "preScoop": True, "directSource": True,
            "policySignal": True, "companies": companies, "mentionedCompanies": mentions,
            "signalType": "iris_rnd_announcement", "category": "정책·규제",
            "dateSource": "IRIS 공고일자", "announcementId": ann_id,
            "announcementFields": fields, "bodyText": body,
            "programName": fields.get("내역사업명") or fields.get("사업공고명", ""),
            "eligibility": fields.get("지원대상") or fields.get("지원 대상") or fields.get("자격조건", ""),
            "applicationPeriod": fields.get("접수기간", ""),
            "verification": "공개 원자료 추적 — 공모 공고이며 기업 참여·선정 및 단독 여부 미확인",
            "evidenceLimitations": ["첨부문서는 수집하지 않음", "기업명 언급은 참여·선정의 증거가 아님"],
        })
    diag["retained"] = min(len(out), max_items)
    diag["recordsSkippedByLimit"] = max(0, len(out) - max_items)
    if not diag["listPagesParsed"]:
        status = "list_fetch_or_parse_failed"
    elif not announcements:
        status = "invalid_detail_ids" if diag["invalidIds"] else "empty_official_list"
    elif not diag["detailCandidates"]:
        status = "no_recent_publications_in_checked_list"
    elif not diag["detailPagesFetched"] and not diag["detailReused"]:
        status = "detail_fetch_failed"
    elif not diag["datedRecords"]:
        status = "detail_parse_failed"
    elif not diag["recentRecords"]:
        status = "no_recent_publications_in_checked_details"
    else:
        status = "recent_announcements_checked"
    diag["status"] = status
    diag["collectionComplete"] = not (diag["coverageLimited"] or diag["errors"] or diag["invalidIds"] or diag["recordsSkippedByLimit"]
        or any(reason not in ("outside_lookback", "no_company_or_industry_in_title") for reason in diag["exclusions"]))
    print(f"direct IRIS scout: diagnostics={diag}")
    return out[:max_items]



def court_article(page_text):
    """대법원 보도자료 본문만: '조회수 N' 뒤부터 '이전글'·'다음글'·'목록' 앞까지(메뉴·바닥글·옆 글 제목 빼고). 못 찾으면 ''.
    운영 10-31: 쪽 전체를 낱말 대조에 써서 메뉴의 '회생·파산 공고'·'특허법원'·'법원전시관'이 모든 보도자료에 걸렸다
    ('파키스탄 대법원장 방문'·'법원경매 기일입찰표 양식 전면 개선'이 단서로 남음). 요약도 메뉴 3,500자였다."""
    m = re.search(r"조회수\D{0,5}\d[\d,]*", page_text or "")
    if not m:
        return ""
    rest = page_text[m.end():]
    end = re.search(r"이전글|다음글|목록\s*대법원\s*페이스북|개인정보처리방침", rest)
    body = (rest[:end.start()] if end else rest[:6000]).strip()
    head = re.match(r"[\s|:]*첨부파일[\s|:]*", body)
    if head:  # 첨부 파일 이름(띄어쓰기 포함)들을 뗀다
        body = body[head.end():]
        while True:
            m2 = re.match(r"[^□▣○●◇◆■]{0,200}?\.(?:pdf|hwpx?|zip)\b[\s|,\])]*", body, re.I)
            if not m2:
                break
            body = body[m2.end():]
    return body.strip()


COURT_BODY = "article"  # 저장 항목 표시: 본문만으로 고른 것(이 표시 없는 옛 저장분은 본문을 다시 읽는다)


def dedup_items(items):
    """Same group + title once. A later item (the earlier run's carry-over) replaces an earlier one, except that a
    title-only court release never replaces one whose body was read in this run."""
    dedup = {}
    for x in items:
        key = (x["sourceGroup"], re.sub(r"[^가-힣A-Za-z0-9]", "", x["title"]).lower())
        if dedup.get(key, {}).get("bodyFrom") == COURT_BODY and x.get("bodyFrom") != COURT_BODY:
            continue
        dedup[key] = x
    return sorted(dedup.values(), key=lambda x: x["published"], reverse=True)[:80]


def keep_prior(item, now):
    """Rolling carry-over of an earlier run's item. Items made by a parser version since fixed are dropped
    (they come back only when the source is read again with the current parser)."""
    if not isinstance(item, dict):
        return False
    dt=parse_dt(item.get("published"))
    if dt.year<2000 or dt<now-timedelta(days=LOOKBACK_DAYS) or dt>now+timedelta(hours=6):
        return False
    if resurfaced_historical_original(item.get("title"),dt):
        return False
    if item.get("signalType")=="official_recall_notice" and item.get("dateParseVersion")!="sequence-v2":
        return False
    # 메뉴까지 낱말 대조에 쓴 옛 대법원 보도자료(10-31 운영 6건 — '파키스탄 대법원장 방문' 등)는 이어 싣지 않는다.
    # 목록이 열리면 본문만으로 다시 고른다. 목록이 안 열리면 그 칸은 미확인(진단에 오류)으로 남는다.
    if item.get("signalType")=="supreme_court_case_release" and item.get("bodyFrom") not in (COURT_BODY, "title"):
        return False
    return True


def fetch_direct_court(max_items=12, prior_items=None):
    """Collect date-stamped Supreme Court releases and industry-related disputes."""
    base="https://www.scourt.go.kr"
    page_paths=[
        "/supreme/news/NewsListAction.work?gubun=702",
        "/portal/news/NewsListAction.work?gubun=6",
    ]
    now=datetime.now(KST)
    cutoff=now-timedelta(days=LOOKBACK_DAYS)
    diag={"pagesAttempted":0,"pagesFetched":0,"rowsScanned":0,"datedRows":0,
          "recentRows":0,"detailPagesAttempted":0,"detailPagesFetched":0,"retained":0,
          "errors":[],"sampleRows":[]}
    DIRECT_DIAGNOSTICS["scourt-case-releases"]=diag
    # 이전 실행에서 본문까지 읽어 남긴 보도자료(같은 주소·제목·게시일)는 다시 열지 않는다.
    # 운영 10-28: 같은 본문 한 쪽('경매 임차인 통지서 전면 개선')이 세 번 중 두 번 Connection reset.
    cache={it.get("url"):it for it in (prior_items or [])
           if isinstance(it,dict) and it.get("signalType")=="supreme_court_case_release" and it.get("url")}
    out=[];seen=set()
    date_re=re.compile(r"20\d{2}\s*[-./]\s*\d{1,2}\s*[-./]\s*\d{1,2}")
    anchor_re=re.compile(r'<a\b[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',re.I|re.S)
    material_re=re.compile(
        r"자동차|모빌리티|전기차|배터리|타이어|철강|강관|변압기|전력기기|전선|케이블|"
        r"풍력|태양광|원전|원자력|SMR|에너지|산업재해|중대재해|산업안전|하도급|공정거래|"
        r"담합|영업비밀|특허|상표|기술유출|공급계약|공사대금|산업단지|환경오염|폐기물|"
        r"탄소|노동조합|임금|정리해고|구조조정|회생|파산|손해배상|추심금|계약해지",
        re.I,
    )
    ignore_title_re=re.compile(r"임명식|인사발령|포토뉴스|사법연감|인사말|행사|기념식",re.I)
    for path in page_paths:
        if len(out)>=max_items: break
        page_url=base+path
        diag["pagesAttempted"]+=1
        page=None
        # scourt.go.kr drops some runner connections (운영 10-28: 14:28 두 쪽 모두 timed out, 직후 탐침은 1~2초에 200,
        # 6번 중 1번 ConnectionError). One slower retry before calling the page failed.
        for attempt,timeout in ((1,10),(2,20)):
            try:
                page=decode_web_bytes(get(page_url,timeout=timeout))
                diag["pagesFetched"]+=1
                if attempt>1:
                    diag["retriedOk"]=diag.get("retriedOk",0)+1
                break
            except Exception as exc:
                if attempt==2 and len(diag["errors"])<4:
                    diag["errors"].append(f"{path}: {type(exc).__name__}: {exc}"[:240])
                if attempt==1:
                    time.sleep(3)
        if page is None:
            continue
        rows=re.findall(r"<tr\b[^>]*>.*?</tr>",page,re.I|re.S)
        for row in rows:
            diag["rowsScanned"]+=1
            links=list(anchor_re.finditer(row))
            if not links: continue
            date_match=date_re.search(row)
            if not date_match: continue
            try:
                date_value=re.sub(r"\s*[-./]\s*","-",date_match.group(0)).strip()
                dt=datetime.strptime(date_value,"%Y-%m-%d").replace(tzinfo=KST)
            except ValueError:
                continue
            diag["datedRows"]+=1
            if dt<cutoff or dt>now+timedelta(hours=6): continue
            candidates=[]
            for link in links:
                title=clean(link.group(2))
                href=urllib.parse.urljoin(base,html.unescape(link.group(1).strip()))
                if len(title)<8 or re.search(r"첨부|다운로드|바로가기|이미지|아이콘|목록|이전|다음",title,re.I):
                    continue
                if href.lower().endswith((".pdf",".hwp",".hwpx",".zip")):
                    continue
                if "NewsViewAction.work" not in href and "newsView" not in href:
                    continue
                candidates.append((title,href))
            if not candidates: continue
            title,href=max(candidates,key=lambda item:len(item[0]))
            if href in seen or ignore_title_re.search(title): continue
            diag["recentRows"]+=1
            seen.add(href)
            hit=cache.get(href)
            if (hit and hit.get("title")==title and str(hit.get("published",""))[:10]==dt.date().isoformat()
                    and hit.get("bodyFrom")==COURT_BODY):
                diag["detailReused"]=diag.get("detailReused",0)+1
                out.append(dict(hit))
                if len(out)>=max_items: break
                continue
            detail=""
            detail_failed=False
            title_companies=target_hits(title)
            if not title_companies and diag["detailPagesAttempted"]<8:
                diag["detailPagesAttempted"]+=1
                # 본문 쪽도 같은 연결 끊김이 난다(운영 10-28 20:36: 목록 2/2 성공, 본문 1건 Connection reset). 한 번만 더.
                for attempt,timeout in ((1,8),(2,15)):
                    try:
                        detail=court_article(clean(decode_web_bytes(get(href,timeout=timeout))))[:12000]
                        diag["detailPagesFetched"]+=1
                        if attempt>1:
                            diag["retriedOk"]=diag.get("retriedOk",0)+1
                        break
                    except Exception as exc:
                        if attempt==2:
                            detail_failed=True
                            if len(diag["errors"])<4:
                                diag["errors"].append(f"detail {title[:50]}: {type(exc).__name__}: {exc}"[:240])
                        if attempt==1:
                            time.sleep(2)
            body=title+" "+detail
            companies=target_hits(body)
            # '대법원 선고 … 사건에 관한 보도자료'는 그 자체가 판결이다. 본문이 끊겨도(운영 10-31: 3건 Connection reset)
            # 제목의 업종 낱말(중대재해 등)로는 고른다 — 이 경우 bodyFrom='title'로 남겨 다음 실행에 본문을 다시 읽는다.
            if not SIGNAL_TERMS.search(body) and "선고" not in title: continue
            if not companies and not material_re.search(body):
                if len(diag["sampleRows"])<8:
                    diag["sampleRows"].append({"title":title[:160],"date":dt.isoformat(),
                                                "reason":"not a tracked-company or industry-related dispute"})
                continue
            out.append({
                "sourceName":"대법원 보도자료","officialLabel":"대한민국 법원",
                "querySite":"scourt.go.kr","sourceGroup":"법원·분쟁",
                "title":title,"url":href,"published":dt.isoformat(),
                "summary":detail[:3500],"official":True,"preScoop":True,
                "companies":companies,"directSource":True,
                "signalType":"supreme_court_case_release","bodyFrom":"title" if detail_failed else COURT_BODY,
                **({"detailError":"본문 못 읽음(연결 끊김) — 제목만으로 고름"} if detail_failed else {}),
                "dateSource":"대법원 보도자료 게시일"
            })
            if len(out)>=max_items: break
    diag["retained"]=len(out)
    print(f"direct Supreme Court case scout: diagnostics={diag}")
    return out


def fetch_direct_nlrc(max_items=12):
    """Read actual NLRC published case-list rows, not navigation links.

    The case search/index.do pages are search forms. Their hyperlinks do not
    contain dated judgment records, so scraping anchor neighbors returned zero
    dated results even when the official case listing had older records.
    """
    base="https://nlrc.go.kr"
    page_paths=[
        "/nlrc/mainCase/mainJudgment/list.do",
        "/nlrc/jeonnam/mainCase/judgment/index.do",
        "/nlrc/mainCase/judgment/search/index.do",
    ]
    now=datetime.now(KST)
    cutoff=now-timedelta(days=LOOKBACK_DAYS)
    diag={"pagesAttempted":0,"pagesFetched":0,"rowsScanned":0,"datedRows":0,
          "recentRows":0,"outsideWindow":0,"industryRelevantRows":0,
          "detailPagesFetched":0,"retained":0,"latestPublished":"",
          "errors":[],"sampleRows":[]}
    DIRECT_DIAGNOSTICS["nlrc-case-summaries"]=diag
    out=[];seen=set()
    date_re=re.compile(r"20\d{2}\s*[-./]\s*\d{1,2}\s*[-./]\s*\d{1,2}")
    anchor_re=re.compile(r'<a\b[^>]*href=["\x27]([^"\x27]*)["\x27][^>]*>(.*?)</a>',re.I|re.S)
    industry_re=re.compile(
        r"자동차|전기차|배터리|철강|강관|변압기|전력기기|전선|케이블|풍력|태양광|"
        r"원전|원자력|에너지|제조업|생산직|공장|산업재해|중대재해|하도급|협력업체|"
        r"사업장|구조조정|정리해고|임금체불|노동조합|단체교섭|교섭요구|부당노동행위|산업안전",
        re.I,
    )
    for path in page_paths:
        if len(out)>=max_items: break
        page_url=base+path
        diag["pagesAttempted"]+=1
        try:
            page=decode_web_bytes(get(page_url,timeout=10))
            diag["pagesFetched"]+=1
        except Exception as exc:
            if len(diag["errors"])<4:
                diag["errors"].append(f"{path}: {type(exc).__name__}: {exc}"[:240])
            continue
        # Each HTML table row has its own publication date; never borrow a
        # date from the previous or next case or from the current page header.
        for row in re.findall(r"<tr\b[^>]*>.*?</tr>",page,re.I|re.S):
            diag["rowsScanned"]+=1
            row_text=clean(row)
            dm=date_re.search(row_text)
            if not dm:
                continue
            try:
                dt=parse_dt(re.sub(r"\s*[-./]\s*","-",dm.group(0)))
            except ValueError:
                continue
            if dt.year<2000:
                continue
            diag["datedRows"]+=1
            if not diag["latestPublished"] or dt.isoformat()>diag["latestPublished"]:
                diag["latestPublished"]=dt.isoformat()
            links=[(clean(m.group(2)),html.unescape(m.group(1).strip()))
                   for m in anchor_re.finditer(row)]
            links=[(t,href) for t,href in links
                   if len(t)>=15 and not re.search(r"목록|더보기|전체보기|검색|파일|첨부",t)]
            if links:
                title,raw_href=max(links,key=lambda item:len(item[0]))
            else:
                title=re.sub(r"^\s*[\d,]+\s*", "", row_text)
                title=re.sub(date_re, "", title).strip()[:220]
                raw_href=""
            if len(title)<15:
                continue
            if dt<cutoff or dt>now+timedelta(hours=6):
                diag["outsideWindow"]+=1
                if len(diag["sampleRows"])<5:
                    diag["sampleRows"].append({"title":title[:130],"date":dt.isoformat(),"reason":"outside lookback"})
                continue
            diag["recentRows"]+=1
            key=re.sub(r"[^가-힣A-Za-z0-9]","",title).lower()
            if key in seen:
                continue
            seen.add(key)
            companies=target_hits(title)
            if not companies and not industry_re.search(title):
                continue
            if not SIGNAL_TERMS.search(title):
                continue
            diag["industryRelevantRows"]+=1
            # A JS-only detail control is not a valid public URL: link to the
            # official dated case list instead of inventing a detail endpoint.
            url=urllib.parse.urljoin(base,raw_href) if raw_href and not raw_href.lower().startswith(("javascript:","#")) else page_url
            if urllib.parse.urlparse(url).hostname not in ("nlrc.go.kr","www.nlrc.go.kr"):
                url=page_url
            out.append({
                "sourceName":"중앙·지방노동위원회 주요판정사례",
                "officialLabel":"노동위원회","querySite":"nlrc.go.kr",
                "sourceGroup":"중앙노동위","title":title,"url":url,
                "published":dt.isoformat(),"summary":row_text[:3500],
                "official":True,"preScoop":True,"companies":companies,
                "directSource":True,"policySignal":not bool(companies),
                "signalType":"nlrc_dated_case_listing","category":"노동·분쟁",
                "dateSource":"노동위원회 판정사례 게시일"
            })
            if len(out)>=max_items:
                break
    diag["retained"]=len(out)
    if diag["datedRows"] and not diag["recentRows"]:
        diag["status"]="official_case_lists_have_no_records_inside_21_day_window"
    elif not diag["datedRows"]:
        diag["status"]="date_rows_not_parsed"
    else:
        diag["status"]="recent_cases_checked"
    print(f"direct NLRC case scout: diagnostics={diag}")
    return out



def fetch_direct_ieps(max_items=12):
    """Read dated notice/permit-trend lists from the official integrated environment-permit system."""
    base="https://ieps.nier.go.kr"
    page_paths=[
        "/web/board/1/",
        "/web/board/5/?CERT_TYP=3&pMENUMST_ID=95&tab=four",
    ]
    now=datetime.now(KST)
    cutoff=now-timedelta(days=LOOKBACK_DAYS)
    diag={"pagesAttempted":0,"pagesFetched":0,"anchorsScanned":0,"datedLinks":0,
          "recentLinks":0,"detailPagesFetched":0,"retained":0,"errors":[],"sampleRows":[]}
    DIRECT_DIAGNOSTICS["ieps-permits"]=diag
    out=[];seen=set()
    anchor_re=re.compile(r'<a\b[^>]+href=["\']([^"\']*)["\'][^>]*>(.*?)</a>',re.I|re.S)
    date_re=re.compile(r"20\d{2}\s*[-./]\s*\d{1,2}\s*[-./]\s*\d{1,2}")
    material_re=re.compile(
        r"통합환경허가|허가재검토|허가배출기준|변경허가|배출시설|배출기준|공정변경|"
        r"사업장\s*(?:허가|증설|변경)|증설\s*(?:허가|사업장)|환경영향평가|배출량",
        re.I,
    )
    for path in page_paths:
        if len(out)>=max_items: break
        url=base+path
        diag["pagesAttempted"]+=1
        try:
            page=decode_web_bytes(get(url,timeout=12))
            diag["pagesFetched"]+=1
        except Exception as exc:
            if len(diag["errors"])<4:
                diag["errors"].append(f"{path}: {type(exc).__name__}: {exc}"[:240])
            continue
        for match in anchor_re.finditer(page):
            diag["anchorsScanned"]+=1
            title=clean(match.group(2))
            href=urllib.parse.urljoin(base,html.unescape(match.group(1).strip()))
            if len(title)<8 or href==url or href in seen:
                continue
            if re.search(r"로그인|회원가입|검색|바로가기|개인정보처리방침|전체메뉴|이전글|다음글",title):
                continue
            context=page[max(0,match.start()-380):min(len(page),match.end()+700)]
            date_match=date_re.search(context)
            if not date_match:
                continue
            try:
                date_value=re.sub(r"\s*[-./]\s*","-",date_match.group(0)).strip()
                dt=datetime.strptime(date_value,"%Y-%m-%d").replace(tzinfo=KST)
            except ValueError:
                continue
            diag["datedLinks"]+=1
            if dt<cutoff or dt>now+timedelta(hours=6):
                continue
            diag["recentLinks"]+=1
            seen.add(href)
            detail=""
            try:
                detail=clean(decode_web_bytes(get(href,timeout=8)))[:12000]
                diag["detailPagesFetched"]+=1
            except Exception:
                pass
            body=title+" "+detail
            companies=target_hits(body)
            # Do not promote routine environmental notices: require a named tracked
            # company or a concrete permit/discharge/process change signal.
            if not companies and not material_re.search(body):
                if len(diag["sampleRows"])<8:
                    diag["sampleRows"].append({"title":title[:160],"date":dt.isoformat(),
                                                "reason":"no tracked company or permit-change signal"})
                continue
            if not SIGNAL_TERMS.search(body):
                continue
            out.append({
                "sourceName":"통합환경허가시스템","officialLabel":"통합환경허가시스템",
                "querySite":"ieps.nier.go.kr","sourceGroup":"환경·인허가","title":title,
                "url":href,"published":dt.isoformat(),"summary":detail[:3500],
                "official":True,"preScoop":True,"companies":companies,
                "directSource":True,"signalType":"ieps_permit_signal",
                "category":"인허가·환경","dateSource":"통합환경허가시스템 게시일"
            })
            if len(out)>=max_items: break
    diag["retained"]=len(out)
    print(f"direct IEPS permit scout: diagnostics={diag}")
    return out


def fetch_direct_factoryon(max_items=12):
    """Read FactoryON's dated public notices and industrial-land sale/disposal notices."""
    base="https://www.factoryon.go.kr"
    page_paths=[
        "/mobile/bbs/lttotNdDspsPblancList.do",
        "/mobile/main/main.do",
        "/mobile/bbs/noticeBbsList.do",
    ]
    now=datetime.now(KST)
    cutoff=now-timedelta(days=LOOKBACK_DAYS)
    diag={"pagesAttempted":0,"pagesFetched":0,"anchorsScanned":0,"datedLinks":0,
          "recentLinks":0,"detailPagesFetched":0,"retained":0,"errors":[],"sampleRows":[]}
    DIRECT_DIAGNOSTICS["factoryon-industrial-sites"]=diag
    out=[];seen=set()
    anchor_re=re.compile(r'<a\b[^>]+href=["\']([^"\']*)["\'][^>]*>(.*?)</a>',re.I|re.S)
    date_re=re.compile(r"20\d{2}\s*[-./]\s*\d{1,2}\s*[-./]\s*\d{1,2}")
    material_re=re.compile(
        r"공장등록현황통계|산업단지|산업시설용지|산업용지|지식산업센터|공장설립|공장등록|입주계약|"
        r"공장\s*(?:신설|증설|이전)|분양|처분|공급공고|임대\s*공고|생산시설",
        re.I,
    )
    ignore_re=re.compile(r"시스템\s*점검|로그인|회원가입|개인정보|위변조|서비스\s*중단|오류\s*안내",re.I)
    for path in page_paths:
        if len(out)>=max_items: break
        url=base+path
        diag["pagesAttempted"]+=1
        try:
            page=decode_web_bytes(get(url,timeout=12))
            diag["pagesFetched"]+=1
        except Exception as exc:
            if len(diag["errors"])<4:
                diag["errors"].append(f"{path}: {type(exc).__name__}: {exc}"[:240])
            continue
        for match in anchor_re.finditer(page):
            diag["anchorsScanned"]+=1
            title=clean(match.group(2))
            href=urllib.parse.urljoin(base,html.unescape(match.group(1).strip()))
            if len(title)<8 or href==url or href in seen or ignore_re.search(title):
                continue
            if not material_re.search(title):
                continue
            # FactoryON uses different list-card markup between desktop and mobile.
            # Prefer the closest visible date within a wider homepage list window.
            left=max(0,match.start()-1600)
            right=min(len(page),match.end()+2200)
            context=page[left:right]
            date_matches=list(date_re.finditer(context))
            if not date_matches:
                if len(diag["sampleRows"])<8:
                    diag["sampleRows"].append({"title":title[:160],"reason":"material title but no nearby publication date"})
                continue
            date_match=min(date_matches,key=lambda item:abs(left+item.start()-match.start()))
            try:
                date_value=re.sub(r"\s*[-./]\s*","-",date_match.group(0)).strip()
                dt=datetime.strptime(date_value,"%Y-%m-%d").replace(tzinfo=KST)
            except ValueError:
                continue
            diag["datedLinks"]+=1
            if dt<cutoff or dt>now+timedelta(hours=6):
                continue
            diag["recentLinks"]+=1
            seen.add(href)
            detail=""
            try:
                detail=clean(decode_web_bytes(get(href,timeout=8)))[:10000]
                diag["detailPagesFetched"]+=1
            except Exception:
                pass
            body=title+" "+detail
            companies=target_hits(body)
            # These are leads for plant/industrial-site follow-up, not scoops by
            # themselves. Generic IT/service notices and untimed static pages fail above.
            if not material_re.search(body):
                continue
            out.append({
                "sourceName":"FACTORY ON(한국산업단지공단)",
                "officialLabel":"팩토리온","querySite":"factoryon.go.kr",
                "sourceGroup":"공장·산업단지","title":title,"url":href,
                "published":dt.isoformat(),"summary":detail[:3500],
                "official":True,"preScoop":True,"companies":companies,
                "directSource":True,"signalType":"factoryon_site_or_registration_notice",
                "category":"인허가·환경" if re.search(r"공장등록|공장\s*(?:신설|증설|이전)|입주계약",title) else "조달·발주",
                "dateSource":"팩토리온 공지·공고 게시일"
            })
            if len(out)>=max_items: break
    diag["retained"]=len(out)
    print(f"direct FactoryON industrial-site scout: diagnostics={diag}")
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
        "rssRejectInvalid":0,"rssRejectOutsideWindow":0,"rssRejectNoCompany":0,"rssRejectNoSignalTerm":0,"rssRejectSamples":[],
        "bingQueries":0,"bingResultBlocks":0,"bingParsedBlocks":0,"bingAccepted":0,
        "bingRejectMalformed":0,"bingRejectUndated":0,"bingRejectOffDomain":0,"bingRejectOutsideWindow":0,"bingRejectNoCompany":0,"bingRejectNoSignalTerm":0,"bingRejectSamples":[],
        "bingQueryDiagnostics":[],
        "errors":[]
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
            parsed=parse_feed(root,domain,group,now,diag)
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
            parsed=parse_feed(root,domain,group,now,diag)
            diag["rssAccepted"]+=len(parsed)
            for h in parsed: add(h)
        except Exception as e:
            record_error("Google RSS signal query",e)

    # 3) General web search fallback.
    # A long OR over company names is too ambiguous for Bing (e.g. "OCI"
    # returns unrelated OCI Services pages) and can cause it to ignore site:.
    # Search the official domain by event terms first; use one rotating,
    # quoted company batch as a second query. Strict destination-host checks
    # below remain mandatory in both cases.
    if len(out)<max_items and ENABLE_BING_FALLBACK:
        target_companies=[
            c for c in company_batches[0]
            if not re.fullmatch(r"[A-Z]{2,3}",str(c).strip())
        ]
        bing_queries=[f"site:{domain} ({terms})"]
        if target_companies:
            quoted_companies=" OR ".join('"'+c.replace('"','')+'"' for c in target_companies[:6])
            bing_queries.append(f"site:{domain} ({quoted_companies}) ({terms})")
        for q in bing_queries[:2]:
            url="https://www.bing.com/search?q="+urllib.parse.quote(q)+"&setlang=ko-KR"
            diag["bingQueries"]+=1
            try:
                raw=get(url)
                result_blocks=list(re.finditer(rb"<li\b(?=[^>]*class=[\"'][^\"']*\bb_algo\b[^\"']*[\"'])[^>]*>.*?</li>",raw,re.I|re.S))
                diag["bingResultBlocks"]+=len(result_blocks)
                if len(diag.setdefault("bingQueryDiagnostics",[]))<3:
                    raw_text=raw.decode("utf-8","ignore")
                    title_match=re.search(r"<title[^>]*>(.*?)</title>",raw_text,re.I|re.S)
                    result_hosts=[]
                    for block_match in result_blocks[:10]:
                        block=block_match.group(0).decode("utf-8","ignore")
                        link_match=re.search(r'<h2\b[^>]*>\s*<a\b[^>]*href=["\']([^"\']+)["\']',block,re.I|re.S)
                        if not link_match:
                            continue
                        destination=unwrap_bing_link(html.unescape(link_match.group(1)))
                        host=urllib.parse.urlparse(destination).netloc.lower().split(":")[0]
                        if host and host not in result_hosts:
                            result_hosts.append(host)
                    diag["bingQueryDiagnostics"].append({
                        "query":q[:260],
                        "responseTitle":clean(title_match.group(1) if title_match else "")[:160],
                        "responseBytes":len(raw),
                        "resultBlockCount":len(result_blocks),
                        "resultHosts":result_hosts[:8],
                        "requestedDomainPresent":any(official_host_matches("https://"+host+"/",domain) for host in result_hosts),
                    })
                parsed=parse_bing_html(raw,domain,group,now,diag)
                diag["bingAccepted"]+=len(parsed)
                for h in parsed: add(h)
            except Exception as e:
                record_error("Bing fallback",e)
            if len(out)>=max_items: break

    if not ENABLE_BING_FALLBACK:
        diag["bingFallbackDisabled"] = True
        diag["bingFallbackNote"] = "Disabled by default after repeated off-domain-only results; Google RSS and direct official collectors remain active."
    else:
        diag["bingFallbackDisabled"] = False

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
    diag={"listFetched":False,"rowsScanned":0,"materialTitles":0,"detailPagesFetched":0,"datedRows":0,"recentRows":0,"undatedMaterialRows":0,"retained":0,"errors":[],"sampleRows":[]}
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
        if not title_candidates:
            if len(diag["sampleRows"])<8:
                diag["sampleRows"].append({"reason":"no-material-title","row":clean(row)[:350],"cells":cell_texts[:5],"links":[{"href":html.unescape(h),"title":clean(t)} for h,t in link_matches[:4]]})
            continue
        title=max(title_candidates,key=len)
        diag["materialTitles"]+=1
        href=detail_hrefs[0] if detail_hrefs else list_url
        row_text=clean(row)
        if href in seen:
            continue
        seen.add(href)
        date_match = re.search(r"20\d{2}\s*(?:[-./년])\s*\d{1,2}\s*(?:[-./월])\s*\d{1,2}\s*(?:일)?(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?", row_text)
        detail_text = ""
        if not date_match and detail_hrefs:
            try:
                diag["detailPagesFetched"]+=1
                detail_text = clean(get(href, timeout=8).decode("utf-8", "ignore"))[:16000]
            except Exception as e:
                if len(diag["errors"])<3:
                    diag["errors"].append(f"detail fetch: {type(e).__name__}: {e}")
                detail_text = ""
            date_match = re.search(r"20\d{2}\s*(?:[-./년])\s*\d{1,2}\s*(?:[-./월])\s*\d{1,2}\s*(?:일)?(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?", detail_text)
        if not date_match:
            diag["undatedMaterialRows"]+=1
            if len(diag["sampleRows"])<8:
                diag["sampleRows"].append({"reason":"material-title-but-no-publication-date","title":title[:220],"row":row_text[:350],"links":len(detail_hrefs)})
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

    try:
        earlier = json.loads(OUT.read_text(encoding="utf-8"))
        earlier_items = earlier.get("items", []) if isinstance(earlier, dict) else []
        earlier_dates = ((earlier.get("detailDates") or {}).get("ntis") or {}) if isinstance(earlier, dict) else {}
    except Exception:
        earlier_items, earlier_dates = [], {}

    direct_court = fetch_direct_court(prior_items=earlier_items)
    items.extend(direct_court)
    by_group["법원·분쟁"] = by_group.get("법원·분쟁", 0) + len(direct_court)

    direct_iris = fetch_direct_iris_announcements(prior_items=earlier_items)
    items.extend(direct_iris)
    by_group["R&D·기술"] = by_group.get("R&D·기술", 0) + len(direct_iris)

    direct_ntis = fetch_direct_ntis_announcements(prior_items=earlier_items,
                                                  known_dates=earlier_dates if isinstance(earlier_dates, dict) else {})
    items.extend(direct_ntis)
    by_group["R&D·기술"] = by_group.get("R&D·기술", 0) + len(direct_ntis)

    direct_nlrc = fetch_direct_nlrc()
    items.extend(direct_nlrc)
    by_group["중앙노동위"] = by_group.get("중앙노동위", 0) + len(direct_nlrc)

    direct_ieps = fetch_direct_ieps()
    items.extend(direct_ieps)
    by_group["환경·인허가"] = by_group.get("환경·인허가", 0) + len(direct_ieps)

    direct_factoryon = fetch_direct_factoryon()
    items.extend(direct_factoryon)
    by_group["공장·산업단지"] = by_group.get("공장·산업단지", 0) + len(direct_factoryon)

    direct_procurement = fetch_direct_kepco_enc()
    items.extend(direct_procurement)
    by_group["공기업·조달"] = by_group.get("공기업·조달", 0) + len(direct_procurement)

    direct_recalls = fetch_direct_car_recalls()
    items.extend(direct_recalls)
    by_group["자동차·결함"] = by_group.get("자동차·결함", 0) + len(direct_recalls)

    freshly_collected_items = list(items)

    # Persist rolling official-source signals across rotating query batches.
    # Old recall records collected by the previous, date-contaminating parser are
    # deliberately discarded unless they carry the current parse-version marker.
    now=datetime.now(KST)
    prior_items=[]
    prior_source_states=None
    try:
        previous=json.loads(OUT.read_text(encoding="utf-8"))
        prior_items=previous.get("items",[]) if isinstance(previous,dict) else []
        prior_source_states=previous.get("sourceObservations") if isinstance(previous,dict) else None
    except Exception:
        prior_items=[]
    items.extend(item for item in prior_items if keep_prior(item, now))

    # Keep the feed compact and deterministic.
    items = dedup_items(items)
    observations=update_source_states(
        prior_source_states,SOURCE_DIAGNOSTICS,DIRECT_DIAGNOSTICS,
        freshly_collected_items,now=now)
    payload = {
        "generatedAt": datetime.now(KST).isoformat(),
        "lookbackDays": LOOKBACK_DAYS,
        "sourceGroups": by_group,
        "sourceDiagnostics": SOURCE_DIAGNOSTICS,
        "directSourceDiagnostics": DIRECT_DIAGNOSTICS,
        "detailDates": DETAIL_DATES,
        "sourceObservations": observations,
        "items": items,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"pre-scoop radar: {sum(by_group.values())} hits / {len(items)} retained / groups={by_group}")

if __name__ == "__main__":
    main()
