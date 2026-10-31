"""Probe 21: USITC EDIS 데이터 웹서비스 — 로그인 없이(익명) 문서 메타데이터가 열리는지, 337-TA-1494 문서 목록·제출자 칸.
EDIS3 웹서비스 안내서: https://edis.usitc.gov/data/{investigation|document}, 익명은 메타데이터만. 저장하지 않음. 키 없음."""
import re
import requests

out = []
UA = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)", "Accept": "application/xml"}
for url in ["https://edis.usitc.gov/data/investigation/337-1494",
            "https://edis.usitc.gov/data/document?investigationNumber=337-1494&pageNumber=1",
            "https://edis.usitc.gov/data/document?investigationNumber=337-1494&pageNumber=2"]:
    try:
        r = requests.get(url, headers=UA, timeout=60)
        t = r.text
        out.append(f"== {url}: HTTP {r.status_code} type={r.headers.get('content-type')} len={len(t)}")
        out.append("tags: " + repr(sorted(set(re.findall(r"<([A-Za-z][A-Za-z0-9]*)[ >]", t)))[:60]))
        docs = re.findall(r"<document>(.*?)</document>", t, re.S)
        out.append(f"documents on page: {len(docs)}")
        for d in docs[:3]:
            out.append("  doc: " + re.sub(r"\s+", " ", d)[:700])
        # 10월 문서만 짧게
        for d in docs:
            dd = re.search(r"<documentDate>(.*?)</documentDate>", d)
            if dd and dd.group(1)[:7] in ("2026-10", "10/0", "10/1"):
                f = {k: (re.search(fr"<{k}>(.*?)</{k}>", d, re.S) or [None, ""])[1][:120] for k in ("id", "documentType", "documentTitle", "firmOrganization", "filedBy", "onBehalfOf", "documentDate", "officialReceivedDate", "securityLevel")}
                out.append("  OCT: " + repr(f))
        if not docs:
            out.append("body: " + t[:800])
    except Exception as e:  # noqa: BLE001
        out.append(f"== {url}: {type(e).__name__} {str(e)[:150]}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:400])
