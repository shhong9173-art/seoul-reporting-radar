"""Probe 37: 공공데이터포털 — 법제처 국가법령정보 공유서비스(15000115)·조달청 나라장터 낙찰정보 서비스 형식. 두 키(G2B_API_KEY·DATA_GO_KR_KEY) 각각.
건수·태그·오류 문구만. 키·공고명·업체명은 출력하지 않는다."""
import json
import os
import re
import time
import xml.etree.ElementTree as ET
import requests

KEYS = {k: os.environ.get(k, "").strip() for k in ("G2B_API_KEY", "DATA_GO_KR_KEY")}
H = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
out = [f"keys: " + ", ".join(f"{k} set={bool(v)}" for k, v in KEYS.items()) + f" same={KEYS['G2B_API_KEY'] == KEYS['DATA_GO_KR_KEY']}"]


def scrub(t):
    for v in KEYS.values():
        if v:
            t = t.replace(v, "<KEY>")
    return re.sub(r"[A-Za-z0-9%+/=]{40,}", "<long>", t)


def call(url, params):
    try:
        return requests.get(url, params=params, headers=H, timeout=40)
    except Exception as e:  # noqa: BLE001
        out.append(f"  {url.rsplit('/', 1)[-1]}: {type(e).__name__} {scrub(str(e))[:100]}")
        return None


LAW = "https://apis.data.go.kr/1170000/law/lawSearchList.do"
for kname, key in KEYS.items():
    if not key:
        continue
    out.append(f"== {kname}")
    for tgt, q in (("law", "전기사업법"), ("admrul", "자동차"), ("expc", "전기")):
        r = call(LAW, {"serviceKey": key, "target": tgt, "query": q, "numOfRows": 5, "pageNo": 1})
        if r is None:
            continue
        head = scrub(r.text[:220]).replace("\n", " ")
        try:
            root = ET.fromstring(r.content)
            kids = [c for c in root if len(c)]
            out.append(f"  law {tgt}: HTTP {r.status_code} root={root.tag} totalCnt={root.findtext('totalCnt')} code={root.findtext('.//resultCode') or root.findtext('.//returnReasonCode')} "
                       f"msg={root.findtext('.//resultMsg') or root.findtext('.//returnAuthMsg') or root.findtext('result')} items={len(kids)} item-tags={[c.tag for c in kids[0]][:16] if kids else []}")
        except ET.ParseError:
            out.append(f"  law {tgt}: HTTP {r.status_code} non-XML head={head!r}")
        time.sleep(1)
    for base in ("https://apis.data.go.kr/1230000/as/ScsbidInfoService", "https://apis.data.go.kr/1230000/ScsbidInfoService"):
        for op in ("getScsbidListSttusThng", "getScsbidListSttusCnstwk", "getScsbidListSttusServc"):
            r = call(f"{base}/{op}", {"serviceKey": key, "numOfRows": 5, "pageNo": 1, "inqryDiv": 1, "inqryBgnDt": "202610290000",
                                      "inqryEndDt": "202610302359", "type": "json"})
            if r is None:
                continue
            head = scrub(r.text[:200]).replace("\n", " ")
            try:
                j = r.json()
                body = (j.get("response") or {}).get("body") or {}
                hdr = (j.get("response") or {}).get("header") or {}
                items = body.get("items") or []
                items = items.get("item", items) if isinstance(items, dict) else items
                items = items if isinstance(items, list) else [items]
                out.append(f"  g2b {base.split('/')[-2]}/{op}: HTTP {r.status_code} code={hdr.get('resultCode')} msg={hdr.get('resultMsg')} total={body.get('totalCount')} "
                           f"keys={sorted(items[0])[:40] if items and isinstance(items[0], dict) else []}")
            except ValueError:
                out.append(f"  g2b {base.split('/')[-2]}/{op}: HTTP {r.status_code} non-JSON head={head!r}")
            time.sleep(1)
        if any("code=00" in x for x in out[-3:]):
            break
text = "\n".join(out)
open("/tmp/probe_out.txt", "w").write(text)
print(text[:300])
