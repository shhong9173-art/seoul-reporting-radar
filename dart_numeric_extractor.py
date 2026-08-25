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
MAX_DOCS = 10

NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*(?:조|억|만|천|백)?\s*(?:원|원?화|달러|USD|EUR|%|명|대|만대|억원|조원|GWh|MWh|kWh|톤|㎡|m²|km)?")
KEYWORD_RE = re.compile(
    r"시설투자|신규시설|출자|유상증자|타법인|지분|생산능력|생산|공장|설비|계약|수주|공급|배터리|ESS|AAM|로보택시|북미|미국|유럽|중국|투자",
    re.I,
)


def fetch_bytes(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "auto-desk-radar/1.0"})
    with urlopen(req, timeout=30) as r:
        return r.read()


def html_to_text(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="ignore")
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def extract_document(receipt_no: str) -> dict:
    if not API_KEY or not receipt_no:
        return {"receiptNo": receipt_no, "numbers": [], "error": "missing api key or receipt"}
    try:
        url = "https://opendart.fss.or.kr/api/document.xml?" + urlencode(
            {"crtfc_key": API_KEY, "rcept_no": receipt_no}
        )
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
                for m in KEYWORD_RE.finditer(text):
                    start = max(0, m.start() - 180)
                    end = min(len(text), m.end() + 280)
                    context = text[start:end]
                    vals = NUMBER_RE.findall(context)
                    vals = [re.sub(r"\s+", "", v) for v in vals]
                    vals = [v for v in vals if re.search(r"\d", v)]
                    for v in vals:
                        numbers[v] = context.strip()
                    if vals:
                        snippets.append({"keyword": m.group(0), "numbers": vals[:8], "context": context.strip()})
        out_numbers = list(numbers.keys())[:30]
        return {"receiptNo": receipt_no, "numbers": out_numbers, "snippets": snippets[:20]}
    except Exception as e:
        return {"receiptNo": receipt_no, "numbers": [], "snippets": [], "error": str(e)}


def main():
    if not IN.exists():
        OUT.write_text(json.dumps({"count": 0, "items": [], "errors": ["dart.json missing"]}, ensure_ascii=False), encoding="utf-8")
        return
    payload = json.loads(IN.read_text(encoding="utf-8"))
    rows = payload.get("items", []) if isinstance(payload, dict) else []
    # Focus on the newest, most useful disclosure types to keep the 30-minute run lightweight.
    priority_words = ("시설투자", "출자", "유상증자", "타법인", "지분", "주요사항보고서", "사업보고서", "분기보고서", "반기보고서")
    rows = sorted(
        rows,
        key=lambda x: (
            not any(w.lower() in str(x.get("reportName", "")).lower() for w in priority_words),
            x.get("date", ""),
        ),
        reverse=False,
    )[:MAX_DOCS]
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(extract_document, r.get("receiptNo", "")): r for r in rows}
        for fut in as_completed(futures):
            base = futures[fut]
            result = fut.result()
            result.update({"corpName": base.get("corpName"), "reportName": base.get("reportName"), "date": base.get("date"), "url": base.get("url")})
            results.append(result)
    results.sort(key=lambda x: x.get("date", ""), reverse=True)
    OUT.write_text(json.dumps({"count": len(results), "items": results}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"DART numeric extraction: {sum(bool(x.get('numbers')) for x in results)} docs with numeric signals / {len(results)} docs inspected")


if __name__ == "__main__":
    main()
