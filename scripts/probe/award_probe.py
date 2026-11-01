"""Probe 76: 정책브리핑 보도자료 OpenAPI(문화체육관광부, 공공데이터 15095295 추정) — 공유 키로 열리는지(활용신청 여부),
응답 칸 이름, 최근 3일 부처별 건수와 공정위·기후에너지환경부 제목 몇 줄(공개 보도자료). 키 값은 출력하지 않는다. 한 번."""
import collections
import datetime as dt
import os
import re
import xml.etree.ElementTree as ET

import requests

KEY = (os.environ.get("DATA_GO_KR_KEY") or os.environ.get("KR_FUEL_API_KEY") or "").strip()
KST = dt.timezone(dt.timedelta(hours=9))
now = dt.datetime.now(KST)
out = [f"key length {len(KEY)}"]
for url in ("https://apis.data.go.kr/1371000/pressReleaseService/pressReleaseList",
            "http://apis.data.go.kr/1371000/pressReleaseService/pressReleaseList"):
    params = {"serviceKey": KEY, "startDate": (now - dt.timedelta(days=3)).strftime("%Y%m%d"), "endDate": now.strftime("%Y%m%d")}
    try:
        r = requests.get(url, params=params, timeout=40, headers={"User-Agent": "newsroom-official-research/1.0"})
        body = r.text
        out.append(f"{url.split(':')[0]} HTTP {r.status_code} len {len(body)} head {re.sub(r'\\s+', ' ', body[:200])}")
        code = re.search(r"<(?:returnReasonCode|resultCode)>([^<]+)<", body)
        out.append(f"  code {code.group(1) if code else None}")
        try:
            root = ET.fromstring(body)
        except ET.ParseError as e:
            out.append(f"  not XML: {e}")
            continue
        items = root.findall(".//NewsItem") or root.findall(".//item")
        out.append(f"  items {len(items)}")
        if items:
            out.append("  fields " + ", ".join(sorted({c.tag for c in items[0]})))
            mins = collections.Counter((i.findtext("MinisterCode") or i.findtext("ministerCode") or "?") for i in items)
            out.append("  ministers " + ", ".join(f"{k}:{v}" for k, v in mins.most_common(25)))
            for i in items:
                m = i.findtext("MinisterCode") or ""
                if re.search(r"공정거래|기후에너지|산업통상|환경", m):
                    out.append(f"  {m} | {(i.findtext('ApproveDate') or '')[:16]} | {(i.findtext('Title') or '')[:70]}")
        break
    except Exception as e:  # noqa: BLE001
        out.append(f"{url.split(':')[0]} {type(e).__name__} {str(e)[:100]}")
open("/tmp/probe_out.txt", "w").write("\n".join(out[:80]))
print("\n".join(out)[:600])
