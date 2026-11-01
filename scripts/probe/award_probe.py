"""Probe 72: can DART show a trading link between a supplier in a court insolvency notice and a beat company?
Counts only (names and companies are not printed): exact corp-name matches, audit/business reports in 3 years,
beat-company mentions in the latest report and how many sit near customer words."""
import io
import json
import os
import re
import time
import zipfile
import xml.etree.ElementTree as ET

import requests

KEY = os.environ.get("DART_API_KEY", "").strip()
NAMES = ["케이아이씨", "보성알앤디", "조영산업", "비케이이엔지", "이웨이브", "아이오토", "레호", "아이제이캐스트", "가온셀",
         "블루오션에코", "삼일씨티에스", "메탈153", "디비아이", "세명테크", "에이씨케이", "디원라이트", "군자모라돈",
         # 10-02 [단독] 기아 1차 협력사(회생 폐지) — 통제용
         "현성테크노"]
BEAT = r"현대자동차|현대차|기아|현대모비스|현대위아|한국지엠|한국GM|HL만도|만도|한국타이어|금호타이어|넥센타이어|현대제철|포스코|LS전선|대한전선|HD현대일렉트릭|LS일렉트릭|두산에너빌리티"
CUSTOMER = r"매출처|거래처|고객|판매처|납품|매출액의|매출의"
out = []


def say(s):
    out.append(s)


def strip(n):
    return re.sub(r"\(주\)|㈜|주식회사|\s", "", n or "")


try:
    r = requests.get("https://opendart.fss.or.kr/api/corpCode.xml", params={"crtfc_key": KEY}, timeout=90)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    root = ET.fromstring(z.read(z.namelist()[0]))
    index = {}
    for el in root.iter("list"):
        index.setdefault(strip(el.findtext("corp_name")), []).append((el.findtext("corp_code"), (el.findtext("stock_code") or "").strip()))
    say(f"corpCode entries {sum(len(v) for v in index.values())}")
except Exception as e:  # noqa: BLE001
    say(f"corpCode failed {type(e).__name__}")
    index = {}

totals = {"names": 0, "matched": 0, "ambiguous": 0, "listed": 0, "withReport": 0, "beatMention": 0, "customerContext": 0}
for i, name in enumerate(NAMES, 1):
    totals["names"] += 1
    hits = index.get(strip(name), [])
    line = f"#{i:02d} corp {len(hits)}"
    if hits:
        totals["matched"] += 1
        totals["ambiguous"] += len(hits) > 1
        totals["listed"] += any(s for _, s in hits)
    reports = 0
    beat = cust = 0
    for code, _ in hits[:3]:
        try:
            lst = requests.get("https://opendart.fss.or.kr/api/list.json", params={"crtfc_key": KEY, "corp_code": code, "bgn_de": "20230101",
                                                                                 "page_count": 100}, timeout=40).json()
            time.sleep(0.4)
        except Exception as e:  # noqa: BLE001
            line += f" list {type(e).__name__}"
            continue
        docs = [d for d in lst.get("list") or [] if re.search(r"감사보고서|사업보고서", d.get("report_nm", ""))]
        reports += len(docs)
        line += f" · status {lst.get('status')} filings {len(lst.get('list') or [])} reports {len(docs)}"
        if not docs:
            continue
        rcp = docs[0]["rcept_no"]
        try:
            dz = requests.get("https://opendart.fss.or.kr/api/document.xml", params={"crtfc_key": KEY, "rcept_no": rcp}, timeout=60)
            time.sleep(0.4)
            zz = zipfile.ZipFile(io.BytesIO(dz.content))
            text = " ".join(re.sub(r"<[^>]+>", " ", zz.read(n).decode("utf-8", "replace")) for n in zz.namelist())
            text = re.sub(r"\s+", " ", text)
        except Exception as e:  # noqa: BLE001
            line += f" doc {type(e).__name__}"
            continue
        for m in re.finditer(BEAT, text):
            beat += 1
            near = text[max(0, m.start() - 80): m.end() + 80]
            cust += bool(re.search(CUSTOMER, near))
        line += f" · doc chars {len(text)} kind {'감사' if '감사' in docs[0]['report_nm'] else '사업'}"
    if reports:
        totals["withReport"] += 1
    if beat:
        totals["beatMention"] += 1
    if cust:
        totals["customerContext"] += 1
    say(line + f" · beat mentions {beat} near customer words {cust}")

say("TOTALS " + json.dumps(totals))
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out[-3:]))
