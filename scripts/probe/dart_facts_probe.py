"""Isolated probe: run dart_filing_facts.enrich on real current leads (no store writes). Prints facts and comparisons."""
import builtins, json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
import dart_filing_facts as f
from dart_lineage import zip_documents
KEY = os.environ["DART_API_KEY"].strip()
cands = [{"id": "1", "kind": "단서", "company": "HD현대일렉트릭", "title": "HD현대일렉트릭 · 타인에대한채무보증결정", "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261026800468"},
         {"id": "2", "kind": "단서", "company": "고려아연", "title": "고려아연 · 소송등의판결ㆍ결정", "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261023801005"},
         {"id": "3", "kind": "단서", "company": "GS", "title": "GS · 임원ㆍ주요주주특정증권등거래계획철회보고서", "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261023000362"},
         {"id": "4", "kind": "단서", "company": "LS일렉트릭", "title": "LS일렉트릭 · 단일판매ㆍ공급계약체결", "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261019800108"},
         {"id": "5", "kind": "단서", "company": "한화솔루션", "title": "한화솔루션 · 타인에대한채무보증결정", "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260908800375"}]
used = f.enrich(cands, KEY, f.load_corp_codes(), fetch_documents=zip_documents, get=requests.get)
for c in cands:
    fl = c.get("filing", {})
    msg = json.dumps({"co": c["company"], "type": fl.get("type"), "facts": fl.get("facts"), "related": fl.get("related"),
                      "compare": fl.get("compare"), "routine": fl.get("routine"), "error": fl.get("error")}, ensure_ascii=False)
    builtins.print(f"::notice title=facts-{c['id']}::{msg[:3800]}")
builtins.print(f"::notice title=facts-used::documents read {used}")
