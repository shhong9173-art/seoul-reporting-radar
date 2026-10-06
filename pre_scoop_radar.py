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

TARGET_TERMS = (
    "현대차 OR 현대자동차 OR 기아 OR 제네시스 OR 현대모비스 OR 현대위아 OR 만도 OR HL만도 "
    "OR 한국GM OR KG모빌리티 OR 벤츠 OR 메르세데스 OR 폭스바겐 OR BMW OR 르노 OR 아우디 OR 혼다 "
    "OR 한국타이어 OR 넥센타이어 OR 금호타이어 OR 현대트랜시스 OR 현대글로비스 "
    "OR 포스코 OR 포스코홀딩스 OR 현대제철 OR KG스틸 OR 세아 OR 세아제강 "
    "OR 고려아연 OR 영풍 OR LS MnM OR LS일렉트릭 OR HD현대일렉트릭 OR 대한전선 OR 효성중공업 OR 일진전기 "
    "OR LS전선 OR LS지주 OR 두산에너빌리티 OR GS OR GS칼텍스 OR 한화솔루션 OR OCI OR OCI홀딩스 OR 씨에스윈드 "
    "OR 태광 OR 동성케미칼 OR DL케미칼 OR LG화학 OR 롯데케미칼 OR 금호석유화학 OR 효성첨단소재 OR 코오롱인더"
)

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
    try:
        d = parsedate_to_datetime(v)
        return d.astimezone(KST) if d.tzinfo else d.replace(tzinfo=KST)
    except Exception:
        try:
            d = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=KST)
        except Exception:
            return datetime.min.replace(tzinfo=KST)

def fetch_source(group, domain, terms, max_items=12):
    now = datetime.now(KST)
    after = (now - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    q = f"site:{domain} ({TARGET_TERMS}) {terms} after:{after}"
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(q) + "&hl=ko&gl=KR&ceid=KR:ko"
    try:
        root = ET.fromstring(get(url))
    except Exception:
        return []
    out = []
    seen = set()
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = item.findtext("pubDate") or ""
        desc = clean(item.findtext("description") or "")
        src = item.find("source")
        source_name = (src.text or "").strip() if src is not None else domain
        if not title or not link:
            continue
        dt = parse_dt(pub)
        if dt < now - timedelta(days=LOOKBACK_DAYS):
            continue
        if not SIGNAL_TERMS.search(title + " " + desc):
            continue
        key = link or (source_name + "|" + title)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "sourceName": source_name,
            "officialLabel": domain,
            "querySite": domain,
            "sourceGroup": group,
            "title": title,
            "url": link,
            "published": dt.isoformat(),
            "summary": desc[:3000],
            "official": True,
            "preScoop": True,
        })
        if len(out) >= max_items:
            break
    return out

def main():
    items = []
    by_group = {}
    for group, domain, terms in SOURCE_SPECS:
        hits = fetch_source(group, domain, terms)
        items.extend(hits)
        by_group[group] = by_group.get(group, 0) + len(hits)
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
        "items": items,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"pre-scoop radar: {sum(by_group.values())} hits / {len(items)} retained / groups={by_group}")

if __name__ == "__main__":
    main()
