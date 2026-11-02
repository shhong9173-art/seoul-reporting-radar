"""Probe 98: 나라장터 낙찰정보 — 물품·공사·용역·외자 낙찰 목록 1주(10-26~10-30)에서 출입처 대기업 이름(전력기기·전선·철강·완성차·타이어)이
낙찰자 칸에 어떻게 적히는지. 출입처 이름 줄만(대기업 법인명·금액·수요기관·공고명 앞부분), 나머지는 건수만."""
import os
import re
from collections import Counter

import requests

KEY = (os.environ.get("G2B_API_KEY") or os.environ.get("CUSTOMS_API_KEY") or "").strip()
H = {"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"}
BASE = "https://apis.data.go.kr/1230000/as/ScsbidInfoService"
BEAT = re.compile(r"엘에스|LS|에이치디현대|HD현대|현대일렉|효성중공업|일진전기|대한전선|가온전선|현대제철|동국제강|동국씨엠|포스코|세아|케이지스틸|KG스틸|"
                  r"현대자동차|기아|한국타이어|넥센타이어|금호타이어|두산에너빌|고려아연|한화솔루션|엘지화학|LG화학", re.I)
out = []
for op in ("getScsbidListSttusThng", "getScsbidListSttusCnstwk", "getScsbidListSttusServc", "getScsbidListSttusFrgcpt"):
    rows, total, err = [], None, None
    for page in (1, 2, 3):
        try:
            r = requests.get(f"{BASE}/{op}", params={"serviceKey": KEY, "numOfRows": "999", "pageNo": str(page), "inqryDiv": "1",
                                                      "inqryBgnDt": "202610260000", "inqryEndDt": "202610302359", "type": "json"}, headers=H, timeout=60)
            j = r.json()
            head = (j.get("response") or {}).get("header") or {}
            body = (j.get("response") or {}).get("body") or {}
            if str(head.get("resultCode")) not in ("00", "0"):
                err = f"code {head.get('resultCode')} {head.get('resultMsg')}"
                break
            items = body.get("items") or []
            if isinstance(items, dict):
                items = items.get("item") or []
            total = body.get("totalCount")
            rows += items
            if len(rows) >= int(total or 0) or not items:
                break
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__} {str(e)[:60]}"
            break
    hits = [x for x in rows if BEAT.search(str(x.get("bidwinnrNm") or ""))]
    names = Counter(str(x.get("bidwinnrNm")) for x in hits)
    out.append(f"{op}: total {total} read {len(rows)} beat-like {len(hits)} err {err}")
    out.append("  names " + ", ".join(f"{n}({c})" for n, c in names.most_common(15)))
    for x in sorted(hits, key=lambda x: -float(x.get("sucsfbidAmt") or 0))[:6]:
        out.append(f"  {x.get('bidwinnrNm')} | {x.get('bidwinnrBizno')} | {x.get('sucsfbidAmt')} | {x.get('dminsttNm')} | {str(x.get('bidNtceNm'))[:40]} | {x.get('fnlSucsfDate')}")
text = "\n".join(out)
if KEY:
    text = text.replace(KEY, "<KEY>")
open("/tmp/probe_out.txt", "w").write(text)
print(text[:600])
