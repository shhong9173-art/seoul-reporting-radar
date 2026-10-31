"""Probe 40: 법제처 공유서비스 — 전체 질의(*·공백)·정렬 값·출입 업종 낱말별 건수(쪽 수 가늠)·법령 질의. 건수·날짜만."""
import os
import time
import xml.etree.ElementTree as ET
import requests

KEY = os.environ.get("G2B_API_KEY", "").strip()
H = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
URL = "https://apis.data.go.kr/1170000/law/lawSearchList.do"
out = []


def q(label, **p):
    t0 = time.time()
    try:
        r = requests.get(URL, params={"serviceKey": KEY, "numOfRows": 100, "pageNo": 1, **p}, headers=H, timeout=40)
        root = ET.fromstring(r.content)
    except Exception as e:  # noqa: BLE001
        out.append(f"{label}: {type(e).__name__}")
        return
    items = [c for c in root if len(c)]
    dk = {"admrul": "발령일자", "law": "공포일자", "expc": "회신일자"}[p["target"]]
    d = [x.findtext(dk) or "" for x in items]
    out.append(f"{label}: code={root.findtext('.//resultCode')} msg={root.findtext('.//resultMsg')} total={root.findtext('totalCnt')} n={len(items)} first3={d[:3]} desc={d == sorted(d, reverse=True)} asc={d == sorted(d)} {time.time() - t0:.1f}s")
    time.sleep(0.7)


q("admrul *", target="admrul", query="*")
q("admrul sort=date", target="admrul", query="자동차", sort="date")
q("admrul sort=ddes", target="admrul", query="자동차", sort="ddes")
q("admrul sort=dasc", target="admrul", query="자동차", sort="dasc")
for kw in ("전기", "전력", "에너지", "철강", "금속", "화학", "화학물질", "배출", "온실가스", "관세", "원산지", "수소", "원자력", "배터리", "이차전지", "광물", "가스", "석유", "산업단지", "타이어"):
    q(f"admrul {kw}", target="admrul", query=kw)
q("law 자동차", target="law", query="자동차")
q("law 전기", target="law", query="전기")
q("law *", target="law", query="*")
q("expc *", target="expc", query="*")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
