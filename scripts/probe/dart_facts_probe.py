"""Isolated probe (branch only, no repo/store writes): dump table label/value rows of real DART filings by type,
so the field extractor is built on the live layout. Public filings only; prints labels and short values."""
import builtins, datetime as dt, json, os, re, sys
from pathlib import Path
from urllib.parse import urlencode
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
from dart_lineage import zip_documents
from dart_contract_tables import CellTableParser

KEY = os.environ["DART_API_KEY"].strip()
OUT = []
def say(*a): OUT.append(" ".join(str(x) for x in a))

TYPES = ["유형자산취득결정", "타법인주식및출자증권취득결정", "신규시설투자", "영업양도", "타법인주식및출자증권처분결정", "유형자산처분결정"]
CORPS = {"현대자동차": "00164742", "엘에스일렉트릭": "00105855", "한화솔루션": "00162461", "포스코홀딩스": "00155319", "현대제철": "00145880",
         "고려아연": "00102858", "대한전선": "00113207", "HD현대일렉트릭": "01205851", "GS": "00500254", "두산에너빌리티": "00159616"}
GIVEN = []

def rows_of(docs):
    out = []
    for d in docs:
        p = CellTableParser(); p.feed(d); p.close()
        for t in p.tables:
            for r in t:
                cells = [c["text"] for c in r]
                if 2 <= len(cells) <= 4 and re.search(r"[가-힣]", cells[0] + (cells[1] if len(cells) > 2 else "")):
                    out.append(" | ".join(c[:50] for c in cells))
    return out

def dump(rcept, label):
    try:
        docs = zip_documents(KEY, rcept)
    except Exception as e:
        say(f"## {label} {rcept} ERROR {type(e).__name__} {str(e)[:80]}"); return
    corp = re.search(r'AREGCIK="(\d{8})"', "".join(docs))
    rows = rows_of(docs)
    say(f"## {label} {rcept} docs={len(docs)} corp={corp.group(1) if corp else None} rows={len(rows)}")
    for r in rows[:28]:
        say("  " + r)

picked = {}
today = dt.date(2026, 10, 27)
for name, code in CORPS.items():
    for ty in ("B", "I"):
        r = requests.get("https://opendart.fss.or.kr/api/list.json", timeout=30, params={"crtfc_key": KEY, "corp_code": code,
            "bgn_de": (today - dt.timedelta(days=700)).strftime("%Y%m%d"), "end_de": today.strftime("%Y%m%d"), "pblntf_ty": ty, "page_count": 100})
        j = r.json()
        if j.get("status") != "000":
            say(f"list {name} {ty} status {j.get('status')} {j.get('message')}"); continue
        for x in j.get("list", []):
            nm = x["report_nm"]
            for t in TYPES:
                if t in nm.replace(" ", "") and t not in picked and "정정" not in nm:
                    picked[t] = (x["rcept_no"], f"{name} {nm.strip()}")
say("picked", json.dumps({k: v[1] for k, v in picked.items()}, ensure_ascii=False))
for r in GIVEN:
    dump(r, "given")
for t, (rc, lab) in picked.items():
    if rc not in GIVEN:
        dump(rc, lab)

chunks, cur = [], ""
for line in OUT:
    if len(cur) + len(line) > 1800:
        chunks.append(cur); cur = ""
    cur += line + " ;; "
chunks.append(cur)
for i, c in enumerate(chunks[:12]):
    builtins.print(f"::notice title=dart-{i}::{c}")
builtins.print(f"::notice title=dart-total::chunks {len(chunks)}")
