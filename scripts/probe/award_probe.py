"""Probe 39: 법제처 공유서비스(공공데이터) 파라미터 — 정렬·날짜 범위·질의 없는 전체·쪽 크기·상세링크 모양. 건수·날짜·부처명·링크 모양만."""
import collections
import os
import re
import time
import xml.etree.ElementTree as ET
import requests

KEY = os.environ.get("G2B_API_KEY", "").strip()
H = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
URL = "https://apis.data.go.kr/1170000/law/lawSearchList.do"
out = []


def scrub(t):
    t = t.replace(KEY, "<KEY>") if KEY else t
    return re.sub(r"\d", "9", t)


def q(label, **p):
    try:
        r = requests.get(URL, params={"serviceKey": KEY, "numOfRows": 100, "pageNo": 1, **p}, headers=H, timeout=40)
        root = ET.fromstring(r.content)
    except Exception as e:  # noqa: BLE001
        out.append(f"{label}: {type(e).__name__} {str(e)[:80]}")
        return []
    items = [c for c in root if len(c)]
    dkey = {"admrul": "발령일자", "law": "공포일자", "expc": "회신일자"}[p["target"]]
    dates = [x.findtext(dkey) or "" for x in items]
    org = {"admrul": "소관부처명", "law": "소관부처명", "expc": "회신기관명"}[p["target"]]
    out.append(f"{label}: HTTP {r.status_code} code={root.findtext('.//resultCode')} totalCnt={root.findtext('totalCnt')} n={len(items)} "
               f"first3={dates[:3]} min={min(dates) if dates else None} max={max(dates) if dates else None} sorted-desc={dates == sorted(dates, reverse=True)}")
    out.append(f"   {org} top: {collections.Counter(x.findtext(org) for x in items).most_common(10)}")
    if items:
        link = [c for c in items[0] if c.tag.endswith("링크")]
        out.append(f"   link shape: {scrub(link[0].text or '') if link else None}; 제개정 {dict(collections.Counter(x.findtext('제개정구분명') for x in items))}")
    time.sleep(1)
    return items


q("admrul no-q default", target="admrul")
q("admrul no-q sort=ddes", target="admrul", sort="ddes")
q("admrul prmlYd Oct", target="admrul", sort="ddes", prmlYd="20261001~20261031")
q("admrul date=20261030", target="admrul", date="20261030")
q("admrul q=고시 sort=ddes", target="admrul", query="고시", sort="ddes")
q("admrul org 산업부 1450000", target="admrul", org="1450000", sort="ddes")
q("law sort=ddes", target="law", sort="ddes")
q("law ancYd Oct", target="law", sort="ddes", ancYd="20261001~20261031")
q("expc sort=ddes", target="expc", sort="ddes")
q("expc q=전기 sort=ddes", target="expc", query="전기", sort="ddes")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
