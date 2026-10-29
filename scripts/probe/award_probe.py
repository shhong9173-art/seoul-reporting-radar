"""격리 탐침 8: 전기위원회(개최결과 PDF·허가대장 PDF)·원안위 회의 목록, 공공데이터포털 건축인허가·공장 필지·우체국 도로명·법정동코드,
영국 Companies House(키 없이). 저장하지 않음. 공개 자료 형식·건수·결과코드만(키 값은 출력하지 않음)."""
import io
import os
import re
import time
import urllib.parse

import requests

out = []


def note(m):
    out.append(m)


def short(s, n=300):
    return re.sub(r"\s+", " ", str(s or ""))[:n]


B = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36", "Accept": "text/html,application/xhtml+xml"}


def pdf_text(raw):
    from pypdf import PdfReader
    return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(raw)).pages)


try:
    r = requests.get("https://www.korec.go.kr/notice/result/selectNoticeList.do", headers=B, timeout=30)
    files = re.findall(r"cf_downloadFile\('(/notice)','([^']+\.pdf)'\)", r.text)
    note(f"KOREC result list HTTP {r.status_code} bytes={len(r.content)} pdfs={len(files)} first={files[:2]}")
    if files:
        path, name = files[0]
        u = "https://www.korec.go.kr/commonfile/fileDownLoad.do?" + urllib.parse.urlencode({"attachingFilePath": path, "attachingFileNm": name})
        p = requests.post(u, headers=B, timeout=60)
        note(f"KOREC pdf HTTP {p.status_code} ctype={p.headers.get('content-type')} bytes={len(p.content)}")
        if p.content[:4] == b"%PDF":
            t = pdf_text(p.content)
            note(f"KOREC result text chars={len(t)} head={short(t, 1500)}")
            note("KOREC 허가 lines=" + short(" // ".join(l for l in t.splitlines() if re.search(r"허가|MW|㎿", l)), 1500))
    r2 = requests.get("https://www.korec.go.kr/notice/selectNoticeList.do", headers=B, timeout=30)
    led = [n for _, n in re.findall(r"cf_downloadFile\('(/notice)','([^']+)'\)", r2.text) if "허가대장" in n]
    note(f"KOREC ledger files={led}")
    if led:
        u = "https://www.korec.go.kr/commonfile/fileDownLoad.do?" + urllib.parse.urlencode({"attachingFilePath": "/notice", "attachingFileNm": led[0]})
        p = requests.post(u, headers=B, timeout=120)
        t = pdf_text(p.content) if p.content[:4] == b"%PDF" else ""
        lines = [short(l, 200) for l in t.splitlines() if l.strip()]
        note(f"KOREC ledger bytes={len(p.content)} chars={len(t)} lines={len(lines)} sample={' // '.join(lines[:3] + lines[40:46])}")
        note("KOREC ledger beat=" + short(" // ".join(l for l in lines if re.search(r"한화|GS|두산|OCI|LS|포스코|현대|고려아연|효성|SK", l)), 1200))
except Exception as e:  # noqa: BLE001
    note(f"KOREC {type(e).__name__} {short(e, 150)}")

try:
    body = "pageNo=1&pagePerCnt=15&MENU_ID=170&CONTENTS_NO=&SITE_NO=2&BOARD_SEQ=14&BBS_SEQ=&USER_NAME=&TEL_NO=&WRITER_DI=&_csrf=&SEARCH_FLD=&SEARCH="
    r = requests.post("https://www.nssc.go.kr/ajaxf/FR_BBS_SVC/BBSViewList.do", data=body, timeout=30,
                      headers={**B, "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest"})
    lst = (r.json().get("data") or {}).get("list") or []
    note(f"NSSC HTTP {r.status_code} rows={len(lst)} first={[x.get('SUBJECT') for x in lst[:3]]}")
except Exception as e:  # noqa: BLE001
    note(f"NSSC {type(e).__name__} {short(e, 150)}")

keys = [(n, os.environ.get(n, "").strip()) for n in ("KR_FUEL_API_KEY", "DATA_GO_KR_KEY", "CUSTOMS_API_KEY", "G2B_API_KEY")]
note("keys present=" + ",".join(n for n, v in keys if v))


def code_of(text):
    m = re.search(r"<(?:resultCode|returnReasonCode)>\s*([^<]+)", text) or re.search(r'"(?:resultCode|returnReasonCode)"\s*:\s*"?([^",}]+)', text)
    return m.group(1).strip() if m else "?"


CALLS = [
    ("건축인허가", "https://apis.data.go.kr/1613000/ArchPmsHubService/getApBasisOulnInfo",
     {"sigunguCd": "44270", "bjdongCd": "25031", "numOfRows": 5, "pageNo": 1, "_type": "json"}),
    ("건축인허가-기간", "https://apis.data.go.kr/1613000/ArchPmsHubService/getApBasisOulnInfo",
     {"sigunguCd": "44270", "bjdongCd": "25031", "startDate": "20260101", "endDate": "20261029", "numOfRows": 5, "pageNo": 1, "_type": "json"}),
    ("공장필지", "https://apis.data.go.kr/B550624/fctryRegistLndpclInfo/getFctryLndpclService",
     {"cmpnyNm": "케이지스틸", "numOfRows": 3, "pageNo": 1, "type": "json"}),
    ("우체국도로명", "http://openapi.epost.go.kr/postal/retrieveNewAdressAreaCdService/retrieveNewAdressAreaCdService/getNewAddressListAreaCd",
     {"searchSe": "road", "srchwrd": "충청남도 당진시 송악읍 북부산업로 1228", "countPerPage": 3, "currentPage": 1}),
    ("법정동코드", "https://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList",
     {"locatadd_nm": "충청남도 당진시 송악읍", "type": "json", "numOfRows": 3, "pageNo": 1}),
]
for label, url, params in CALLS:
    res = []
    for name, key in keys:
        if not key:
            continue
        try:
            r = requests.get(url, params={"serviceKey": urllib.parse.unquote(key), **params}, timeout=40)
            t = r.text
            res.append(f"{name}:HTTP{r.status_code}/{code_of(t)}")
            if r.status_code == 200 and code_of(t) in ("00", "0", "INFO-0", "NORMAL_SERVICE"):
                note(f"DGK {label} ok via {name} body={short(t, 1400)}")
                break
        except Exception as e:  # noqa: BLE001
            res.append(f"{name}:{type(e).__name__}")
        time.sleep(0.5)
    note(f"DGK {label} results={res}")

try:
    r = requests.get("https://api.company-information.service.gov.uk/advanced-search/companies", params={"company_name_includes": "hyosung"}, timeout=30)
    note(f"CH no-key HTTP {r.status_code} {short(r.text, 120)}")
except Exception as e:  # noqa: BLE001
    note(f"CH {type(e).__name__}")

packs, cur = [], ""
for n in out:
    n = n.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(n) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" | " if cur else "") + n
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
