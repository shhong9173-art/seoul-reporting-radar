"""격리 탐침 9: 원안위 목록(세션 쿠키), 우체국 도로명 응답 본문, 전기위원회 허가대장 줄 구조. 공개 자료만."""
import io
import os
import re
import urllib.parse

import requests

out = []


def note(m):
    out.append(m)


def short(s, n=300):
    return re.sub(r"\s+", " ", str(s or ""))[:n]


B = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36", "Accept": "text/html,application/xhtml+xml"}
try:
    s = requests.Session()
    s.headers.update(B)
    r0 = s.get("https://www.nssc.go.kr/ko/cms/FR_CON/index.do?MENU_ID=170", timeout=30)
    csrf = re.search(r'name="_csrf"\s+value="([^"]*)"', r0.text)
    note(f"NSSC index HTTP {r0.status_code} cookies={list(s.cookies.keys())} csrf={'yes' if csrf and csrf.group(1) else 'no'}")
    body = {"pageNo": 1, "pagePerCnt": 15, "MENU_ID": 170, "CONTENTS_NO": "", "SITE_NO": 2, "BOARD_SEQ": 14, "BBS_SEQ": "", "USER_NAME": "", "TEL_NO": "",
            "WRITER_DI": "", "_csrf": csrf.group(1) if csrf else "", "SEARCH_FLD": "", "SEARCH": ""}
    r = s.post("https://www.nssc.go.kr/ajaxf/FR_BBS_SVC/BBSViewList.do", data=body, timeout=30,
               headers={"Accept": "application/json, text/javascript, */*; q=0.01", "X-Requested-With": "XMLHttpRequest",
                        "Referer": "https://www.nssc.go.kr/ko/cms/FR_CON/index.do?MENU_ID=170", "Origin": "https://www.nssc.go.kr"})
    note(f"NSSC list HTTP {r.status_code} ctype={r.headers.get('content-type')} head={short(r.text, 200)}")
    try:
        lst = r.json()["data"]["list"]
        note(f"NSSC rows={len(lst)} first={[x.get('SUBJECT') for x in lst[:3]]}")
    except Exception as e:  # noqa: BLE001
        note(f"NSSC json {type(e).__name__}")
except Exception as e:  # noqa: BLE001
    note(f"NSSC {type(e).__name__} {short(e, 150)}")

key = os.environ.get("CUSTOMS_API_KEY", "").strip()
try:
    r = requests.get("http://openapi.epost.go.kr/postal/retrieveNewAdressAreaCdService/retrieveNewAdressAreaCdService/getNewAddressListAreaCd",
                     params={"serviceKey": urllib.parse.unquote(key), "searchSe": "road", "srchwrd": "충청남도 당진시 송악읍 북부산업로 1228",
                             "countPerPage": 3, "currentPage": 1}, timeout=40)
    note(f"EPOST HTTP {r.status_code} body={short(r.text, 700)}")
except Exception as e:  # noqa: BLE001
    note(f"EPOST {type(e).__name__}")


def pdf_text(raw):
    from pypdf import PdfReader
    return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(raw)).pages)


try:
    r2 = requests.get("https://www.korec.go.kr/notice/selectNoticeList.do", headers=B, timeout=30)
    led = [n for n in re.findall(r"cf_downloadFile\('/notice','([^']+)'\)", r2.text) if "허가대장" in n]
    u = "https://www.korec.go.kr/commonfile/fileDownLoad.do?" + urllib.parse.urlencode({"attachingFilePath": "/notice", "attachingFileNm": led[0]})
    p = requests.post(u, headers=B, timeout=120)
    t = pdf_text(p.content)
    lines = [short(l, 160) for l in t.splitlines() if l.strip()]
    note(f"LEDGER lines={len(lines)} pages≈{t.count(chr(12))}")
    # recent permits: lines with a 2025/2026 date
    recent = [l for l in lines if re.search(r"(?:'|‘|’)?2[56]\.\s?\d{1,2}\.\s?\d{1,2}|202[56]\.\s?\d{1,2}\.\s?\d{1,2}|2[56]\.\d{1,2}\.\d{1,2}", l)]
    note(f"LEDGER recent-date lines={len(recent)} sample={' // '.join(recent[:25])}")
    note(f"LEDGER tail={' // '.join(lines[-15:])}")
except Exception as e:  # noqa: BLE001
    note(f"LEDGER {type(e).__name__} {short(e, 150)}")

packs, cur = [], ""
for n in out:
    n = n.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(n) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" | " if cur else "") + n
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
