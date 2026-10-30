"""probe: 완성차 모델별·공장별 월간 판매 원천(현대차 IR 엑셀, 기아 IR 엑셀) 접근·형식. 공개 자료, 키 없음. 저장하지 않음."""
import io
import json
import sys
import traceback

import requests
from openpyxl import load_workbook

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
out = []


def say(*a):
    out.append(" ".join(str(x) for x in a))


def sheet_dump(name, content, max_rows=90, cols=18, start=0, labels_only=False):
    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    say(f"## {name} sheets={wb.sheetnames}")
    for ws in wb.worksheets[:6]:
        rows = list(ws.iter_rows(values_only=True))
        say(f"# sheet '{ws.title}' rows={len(rows)} cols={max((len(r) for r in rows), default=0)}")
        for i, r in enumerate(rows[start:max_rows], start):
            cells = [("" if v is None else (f"{v:.0f}" if isinstance(v, float) else str(v)).strip()) for v in r[:cols]]
            if labels_only and not (cells[1:2] != [""] or any("total" in c.lower() for c in cells[:4])):
                continue
            if any(cells):
                say(f"{i}|" + "|".join(cells[:5] + (cells[10:13] if labels_only else cells[5:])))


def hmc():
    s = requests.Session()
    s.headers.update(UA)
    for year in ("2026", "2025"):
        r = s.post("https://www.hyundai.com/wsvc/ww/salesPerformance.list.do", data={"lang": "ko", "year": year}, timeout=30)
        say("HMC list", year, r.status_code, len(r.text))
        lst = (r.json().get("data") or {}).get("list") or []
        for x in lst:
            say("  files", {k: v for k, v in x.items() if k.startswith("attr")})
        if year == "2026" and lst:
            x = lst[0]
            for key, rows, start, lab in (("attrSalesModelValue", 170, 90, False), ("attrGlobalPlantValue", 260, 60, True)):
                url = "https://www.hyundai.com" + x[key]
                f = s.get(url, timeout=60)
                say("HMC file", key, f.status_code, len(f.content), f.headers.get("last-modified"))
                if f.status_code == 200:
                    sheet_dump(key, f.content, max_rows=rows, start=start, labels_only=lab)
    r = s.post("https://www.hyundai.com/wsvc/ww/salesPerformanceSummary.item.do", data={"lang": "ko", "year": "2026"}, timeout=30)
    say("HMC summary", r.status_code, r.text[:300])


def kia():
    r = requests.get("https://worldwide.kia.com/api/investors/business-sales-results", params={"year": 0, "page": 0, "language": "ko"}, headers=UA, timeout=30)
    say("KIA list", r.status_code, len(r.text))
    lst = [x for x in (r.json().get("data") or {}).get("list") or [] if x.get("type") == "sales"]
    for x in lst[:3]:
        say("  sales", x.get("year"), x.get("month"), x.get("title"), x.get("publicatedAt"), [f["title"] for f in x.get("files") or []])
    if lst:
        for f in lst[0]["files"]:
            import unicodedata
            title = unicodedata.normalize("NFC", f["title"])
            say("  title nfc", title, "raw==nfc", title == f["title"])
            if "해외공장" in title:
                g = requests.get("https://worldwide.kia.com/files/" + f["path"], headers=UA, timeout=60)
                say("KIA file", title, g.status_code, len(g.content), g.headers.get("last-modified"))
                if g.status_code == 200:
                    sheet_dump(title, g.content, max_rows=200, cols=16)


for fn in (kia,):
    try:
        fn()
    except Exception:  # noqa: BLE001
        say("ERR", fn.__name__, traceback.format_exc()[-600:])

blob = "\n".join(out)
open("/tmp/probe_out.txt", "w").write(blob)
print("total chars", len(blob))
part = int(sys.argv[1]) if len(sys.argv) > 1 else 0
