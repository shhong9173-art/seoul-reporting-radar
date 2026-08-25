from __future__ import annotations

import io
import json
import os
import re
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_KEY = os.environ.get("DART_API_KEY", "").strip()
IN = Path("dart.json")
OUT = Path("dart_numeric.json")
MAX_DOCS = 12

# Only capture material values with an explicit unit. Dates and table row indices are discarded.
VALUE_RE = re.compile(
    r"(?<![A-Za-z0-9])[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*(?:조원|억원|만원|원|조|억|만대|천대|대|%|명|GWh|MWh|kWh|톤|㎡|m²|km|달러|USD|EUR)(?![A-Za-z0-9])",
    re.I,
)
KEYWORD_RE = re.compile(
    r"시설투자|신규시설|출자|유상증자|타법인|지분|생산능력|생산중단|생산|공장|설비|계약|수주|공급|배터리|ESS|AAM|로보택시|북미|미국|유럽|중국|투자",
    re.I,
)
PRIORITY_WORDS = (
    "시설투자", "출자", "유상증자", "타법인", "지분", "생산중단",
    "주요사항보고서", "사업보고서", "분기보고서", "반기보고서", "영업양수도",
)

def fetch_bytes(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "auto-desk-radar/1.0"})
    with urlopen(req, timeout=25) as r:
        return r.read()

def html_to_text(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="ignore")
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    return re.sub(r"\s+", " ", text)

def extract_document(base: dict) -> dict:
    receipt_no = base.get("receiptNo", "")
    if not API_KEY or not receipt_no:
        return {**base, "numbers": [], "snippets": [], "error": "missing api key or receipt"}
    try:
        url = "https://opendart.fss.or.kr/api/document.xml?" + urlencode({"crtfc_key": API_KEY, "rcept_no": receipt_no})
        raw = fetch_bytes(url)
        numbers = {}
        snippets = []
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            for name in z.namelist():
                if not name.lower().endswith((".xml", ".html", ".htm", ".txt")):
                    continue
                try:
                    text = html_to_text(z.read(name))
                except Exception:
                    continue
                for match in KEYWORD_RE.finditer(text):
                    start = max(0, match.start() - 220)
                    end = min(len(text), match.end() + 360)
                    context = text[start:end]
                    vals = [re.sub(r"\s+", "", v) for v in VALUE_RE.findall(context)]
                    vals = list(dict.fromkeys(vals))
                    for value in vals:
                        numbers[value] = context.strip()
                    if vals:
                        snippets.append({"keyword": match.group(0), "numbers": vals[:10], "context": context.strip()})
        return {**base, "numbers": list(numbers.keys())[:40], "snippets": snippets[:24]}
    except Exception as exc:
        return {**base, "numbers": [], "snippets": [], "error": str(exc)}

def main():
    if not IN.exists():
        OUT.write_text(json.dumps({"count": 0, "items": [], "errors": ["dart.json missing"]}, ensure_ascii=False), encoding="utf-8")
        return
    payload = json.loads(IN.read_text(encoding="utf-8"))
    rows = payload.get("items", []) if isinstance(payload, dict) else []
    rows = sorted(
        rows,
        key=lambda x: (
            any(w.lower() in str(x.get("reportName", "")).lower() for w in PRIORITY_WORDS),
            x.get("date", ""),
        ),
        reverse=True,
    )[:MAX_DOCS]
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(extract_document, row) for row in rows]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda x: x.get("date", ""), reverse=True)
    with_numbers = [x for x in results if x.get("numbers")]
    OUT.write_text(json.dumps({"count": len(results), "items": results}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"DART numeric extraction: {len(with_numbers)} docs with material numeric signals / {len(results)} docs inspected")

if __name__ == "__main__":
    main()
