from __future__ import annotations

import html
import io
import json
import os
import re
import time
import zipfile
from xml.etree import ElementTree
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_KEY = os.environ.get("DART_API_KEY", "").strip()
IN = Path("dart.json")
OUT = Path("dart_numeric.json")
MAX_DOCS = 12
# OpenDART status 800 is a service-wide maintenance signal. Once observed,
# stop retrying the same unavailable API for every remaining receipt.
OPENDART_MAINTENANCE_SEEN = False

# Only capture material values with an explicit unit. Dates and table row indices are discarded.
VALUE_RE = re.compile(
    r"(?<![A-Za-z0-9제])[-+]?\d+(?:,\d{3})*(?:\.\d+)?\s*(?:조원|천억원|백억원|십억원|억원|천만원|백만원|만원|천원|원|백만주|만주|천주|주|백만대|만대|천대|대|TWh|GWh|MWh|kWh|GW|MW|kW|kV|MVA|kVA|톤|천톤|만톤|㎡|m²|km²|km|헥타르|달러|USD|EUR|%|명|건|EA)(?![가-힣A-Za-z0-9])",
    re.I,
)
# DART tables frequently put units in a column heading before a bare value:
# "처분예정금액(원) 보통주식 258,750,000". Require an explicit
# unit heading and a nearby financial/quantity field, not arbitrary numbers.
HEADING_VALUE_RE = re.compile(
    r"(?P<label>처분예정금액|처분금액|투자금액|투자금액총액|투자금액\\s*합계|"
    r"취득금액|출자금액|증자금액|발행금액|계약금액|계약총액|거래금액|"
    r"처분예정주식|취득예정주식|처분예정수량|생산능력|투자비용)"
    r"\\s*\\(\\s*(?P<unit>원|백만원|천원|억원|주|천주|만주|MW|GW|톤|대)\\s*\\)"
    r"(?P<tail>.{0,105})",
    re.I | re.S,
)
BARE_TABLE_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])(?P<num>\\d{1,3}(?:,\\d{3})+|\\d{1,9}(?:\\.\\d+)?)(?![A-Za-z0-9.,])")

def extract_heading_values(context: str) -> list[str]:
    values = []
    for match in HEADING_VALUE_RE.finditer(context):
        tail = match.group("tail")
        # Keep the match in its immediate table cell; avoid another numbered
        # disclosure row or a later heading becoming the field's value.
        tail = re.split(r"(?<!\\d)\\b(?:[2-9]|1[0-9])\\s*\\.\\s*(?=[가-힣])", tail, maxsplit=1)[0]
        number = BARE_TABLE_NUMBER_RE.search(tail)
        if not number:
            continue
        unit = match.group("unit")
        value = number.group("num") + unit
        if value not in values:
            values.append(value)
    return values

KEYWORD_RE = re.compile(
    r"시설투자|신규시설|출자|유상증자|타법인|지분|생산능력|생산중단|생산|공장|설비|계약|수주|공급|배터리|ESS|AAM|로보택시|북미|미국|유럽|중국|투자|자기주식|자사주|주식처분|처분예정주식|처분목적|처분예정금액|처분금액",
    re.I,
)
PRIORITY_WORDS = (
    "시설투자", "출자", "유상증자", "타법인", "지분", "생산중단",
    "주요사항보고서", "사업보고서", "분기보고서", "반기보고서", "영업양수도",
)

def fetch_bytes(url: str, timeout: int = 25) -> bytes:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; auto-desk-radar/1.0)", "Accept": "text/html,application/xhtml+xml,application/xml,*/*"})
    with urlopen(req, timeout=timeout) as r:
        return r.read()

def decode_web_bytes(raw: bytes) -> str:
    """Decode Korean government pages without silently discarding legacy-encoded Hangul."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    best = ""
    best_score = -1
    for encoding in ("cp949", "euc-kr", "utf-8"):
        try:
            candidate = raw.decode(encoding, errors="replace")
        except Exception:
            continue
        hangul = sum(1 for ch in candidate if "\uac00" <= ch <= "\ud7a3")
        replacement = candidate.count("\ufffd")
        score = hangul * 4 - replacement * 20
        if score > best_score:
            best, best_score = candidate, score
    return best or raw.decode("utf-8", errors="replace")


def html_to_text(raw: bytes) -> str:
    text = html.unescape(decode_web_bytes(raw))
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    return re.sub(r"\s+", " ", text)


def describe_api_error(raw: bytes) -> tuple[str, str]:
    """Return OpenDART status/message when the endpoint returns XML/JSON instead of ZIP."""
    try:
        root=ElementTree.fromstring(raw)
        status=(root.findtext(".//status") or "").strip()
        message=(root.findtext(".//message") or "").strip()
        if status or message:
            return status, message
    except Exception:
        pass
    try:
        obj=json.loads(raw.decode("utf-8","ignore"))
        if isinstance(obj,dict) and (obj.get("status") or obj.get("message")):
            return str(obj.get("status","")), str(obj.get("message",""))
    except Exception:
        pass
    sample=raw[:180].decode("utf-8","replace").replace("\n"," ").strip()
    return "", f"Expected ZIP but received {sample!r}"

def fetch_dart_viewer_text(receipt_no: str, diagnostics: dict | None = None) -> str:
    """Fallback to the public DART HTML viewer when OpenDART document.xml is unavailable."""
    diag = diagnostics if diagnostics is not None else {}
    diag["attempted"] = True
    receipt_no = str(receipt_no or "").strip()
    if not re.fullmatch(r"\d{14}", receipt_no):
        diag["receiptValid"] = False
        return ""
    diag["receiptValid"] = True
    try:
        main_url = "https://dart.fss.or.kr/dsaf001/main.do?" + urlencode({"rcpNo": receipt_no})
        main_raw = fetch_bytes(main_url, timeout=12)
        main_html = decode_web_bytes(main_raw)
        diag["mainPageBytes"] = len(main_raw)
        lowered = main_html.lower()
        markers = ("viewdoc", "dcmno", "viewer.do", "report/viewer", "iframe", "rcpno", "document_no", "docno")
        diag["mainMarkers"] = {marker: marker in lowered for marker in markers}
        excerpts = []
        for marker in ("viewdoc", "viewer.do", "iframe", "dcmno", "document_no"):
            at = lowered.find(marker)
            if at >= 0:
                excerpt = re.sub(r"\\s+", " ", main_html[max(0, at - 220):min(len(main_html), at + 420)]).strip()
                excerpts.append({"marker": marker, "excerpt": excerpt[:520]})
        diag["mainPageExcerpts"] = excerpts[:5]
        # Capture the actual script initialization around this filing number
        # so future viewer variants can be diagnosed without guessing IDs.
        receipt_positions = [m.start() for m in re.finditer(re.escape(receipt_no), main_html)]
        diag["receiptOccurrences"] = len(receipt_positions)
        diag["receiptExcerpts"] = [
            re.sub(r"\\s+", " ", main_html[max(0, pos - 160):pos + 270])[:430]
            for pos in receipt_positions[:5]
        ]
        diag["tocAssignmentCount"] = len(re.findall(r"\\[['\\\"](?:rcpNo|dcmNo|eleId|offset|length|dtd)['\\\"]\\]", main_html))

    except Exception as exc:
        diag["mainPageError"] = f"{type(exc).__name__}: {exc}"[:240]
        return ""

    # Accept both quoted and unquoted numeric arguments used by different DART viewer builds.
    pattern = re.compile(
        r"viewDoc\(\s*['\"]?(?P<rcp>\d{14})['\"]?\s*,\s*['\"]?(?P<dcm>\d+)['\"]?\s*,"
        r"\s*['\"](?P<ele>[^'\"]*)['\"]\s*,\s*['\"]?(?P<offset>\d+)['\"]?\s*,"
        r"\s*['\"]?(?P<length>\d+)['\"]?\s*,\s*['\"](?P<dtd>[^'\"]*)['\"]\s*\)",
        re.I,
    )
    docs = []
    seen = set()
    for match in pattern.finditer(main_html):
        params = match.groupdict()
        key = (params["dcm"], params["ele"], params["offset"], params["length"], params["dtd"])
        if key in seen:
            continue
        seen.add(key)
        context = main_html[max(0, match.start() - 1200):match.start()]
        labels = re.findall(r"""\btext\s*:\s*(['"])(.{1,120}?)\1""", context, re.I | re.S)
        label = html.unescape(labels[-1][1]).strip() if labels else ""
        params["label"] = re.sub(r"<[^>]+>", " ", label).strip()
        params["tocNo"] = ""
        docs.append(params)

    # Current DART pages often store table-of-contents entries as nodeN['field']
    # assignments instead of literal viewDoc('...') calls. Parse that structure
    # as a fallback, matching receipt number to avoid borrowing another filing's IDs.
    parser_type = "viewDoc-call"
    if not docs:
        node_values = {}
        assignment_re = re.compile(
            r"(?P<node>[A-Za-z_$][\w$]*)\s*\[\s*['\"](?P<field>text|rcpNo|dcmNo|eleId|offset|length|dtd|tocNo)['\"]\s*\]"
            r"\s*=\s*(['\"])(.*?)\3\s*;",
            re.I | re.S,
        )
        for match in assignment_re.finditer(main_html):
            node = match.group("node")
            field = match.group("field")
            value = html.unescape(match.group(4)).strip()
            node_values.setdefault(node, {})[field] = value
        for fields in node_values.values():
            if fields.get("rcpNo") != receipt_no:
                continue
            if not all(fields.get(k) for k in ("dcmNo", "eleId", "offset", "length", "dtd")):
                continue
            docs.append({
                "rcp": fields["rcpNo"],
                "dcm": fields["dcmNo"],
                "ele": fields["eleId"],
                "offset": fields["offset"],
                "length": fields["length"],
                "dtd": fields["dtd"],
                "tocNo": fields.get("tocNo", ""),
                "label": fields.get("text", ""),
            })
        parser_type = "toc-node-assignments"
    diag["parserType"] = parser_type
    diag["documentsFound"] = len(docs)
    diag["documentLabels"] = [d["label"][:80] for d in docs[:8]]

    if not docs:
        diag["reason"] = "no viewDoc() document entries found in DART viewer HTML"
        return ""
    priority = re.compile(r"주요사항보고서|단일판매|공급계약|시설투자|회사분할|생산중단|영업정지|자기주식|자사주|주식처분|투자결정", re.I)
    docs.sort(key=lambda d: (bool(priority.search(d["label"])), bool(d["label"]), -int(d["offset"] or 0)), reverse=True)

    chunks = []
    viewer_errors = []
    pages_fetched = 0
    for doc in docs[:4]:
        query = {
            "rcpNo": doc["rcp"],
            "dcmNo": doc["dcm"],
            "eleId": doc["ele"],
            "offset": doc["offset"],
            "length": doc["length"],
            "dtd": doc["dtd"],
        }
        if doc.get("tocNo"):
            query["tocNo"] = doc["tocNo"]
        url = "https://dart.fss.or.kr/report/viewer.do?" + urlencode(query)
        try:
            raw = fetch_bytes(url, timeout=10)
            body = html_to_text(raw)
            pages_fetched += 1
        except Exception as exc:
            if len(viewer_errors) < 3:
                viewer_errors.append(f"{type(exc).__name__}: {exc}"[:240])
            continue
        if len(body) >= 60:
            chunks.append((doc["label"] + " " + body).strip() if doc["label"] else body)
        if sum(map(len, chunks)) >= 24000:
            break
        time.sleep(0.15)
    viewer_text = re.sub(r"\s+", " ", " ".join(chunks)).strip()[:24000]
    diag["viewerPagesAttempted"] = min(len(docs), 4)
    diag["viewerPagesFetched"] = pages_fetched
    diag["viewerErrors"] = viewer_errors
    diag["viewerTextLength"] = len(viewer_text)
    if not viewer_text:
        diag["reason"] = "viewer entries found but no readable body text returned"
    return viewer_text


def extract_viewer_facts(base: dict, viewer_text: str, error: str, diagnostics: dict | None = None) -> dict:
    numbers = {}
    snippets = []
    for match in KEYWORD_RE.finditer(viewer_text):
        start = max(0, match.start() - 240)
        end = min(len(viewer_text), match.end() + 420)
        context = viewer_text[start:end]
        values = list(dict.fromkeys([re.sub(r"\s+", "", value) for value in VALUE_RE.findall(context)] + extract_heading_values(context)))
        for value in values:
            numbers[value] = context.strip()
        if values and len(snippets) < 24:
            snippets.append({"keyword": match.group(0), "numbers": values[:10], "context": context.strip()})
    return {
        **base,
        "numbers": list(numbers.keys())[:40],
        "snippets": snippets,
        "viewerText": viewer_text[:24000],
        "fallbackSource": "DART HTML viewer",
        "viewerFallbackDiagnostics": diagnostics or {},
        "error": "" if numbers else (error + "; HTML viewer fetched but no values matched configured unit patterns"),
    }


def extract_document(base: dict) -> dict:
    global OPENDART_MAINTENANCE_SEEN
    receipt_no = base.get("receiptNo", "")
    if not API_KEY or not receipt_no:
        return {**base, "numbers": [], "snippets": [], "error": "missing api key or receipt"}
    last_error = "OpenDART status 800: service-wide maintenance circuit breaker is active"
    if OPENDART_MAINTENANCE_SEEN:
        viewer_diag = {}
        viewer_text = fetch_dart_viewer_text(receipt_no, viewer_diag)
        if viewer_text:
            return extract_viewer_facts(base, viewer_text, last_error, viewer_diag)
        return {**base, "numbers": [], "snippets": [], "fallbackSource": "DART HTML viewer attempted", "viewerFallbackDiagnostics": viewer_diag, "error": last_error}
    url = "https://opendart.fss.or.kr/api/document.xml?" + urlencode({"crtfc_key": API_KEY, "rcept_no": receipt_no})
    last_error = "OpenDART document fetch failed"
    for attempt, delay in enumerate((0, 2, 6), start=1):
        if delay:
            time.sleep(delay)
        try:
            raw = fetch_bytes(url)
        except Exception as exc:
            last_error=f"OpenDART document request failed: {type(exc).__name__}: {exc}"
            # Network timeouts can be transient; make the bounded retry attempts.
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                numbers = {}
                snippets = []
                keyword_samples = []
                names = z.namelist()
                parsed_files = 0
                decoded_chars = 0
                keyword_hits = 0
                for name in names:
                    if not name.lower().endswith((".xml", ".html", ".htm", ".txt")):
                        continue
                    try:
                        text = html_to_text(z.read(name))
                    except Exception:
                        continue
                    parsed_files += 1
                    decoded_chars += len(text)
                    for match in KEYWORD_RE.finditer(text):
                        keyword_hits += 1
                        start = max(0, match.start() - 220)
                        end = min(len(text), match.end() + 360)
                        context = text[start:end]
                        vals = [re.sub(r"\s+", "", v) for v in VALUE_RE.findall(context)] + extract_heading_values(context)
                        vals = list(dict.fromkeys(vals))
                        if len(keyword_samples) < 8:
                            keyword_samples.append({
                                "keyword": match.group(0),
                                "numbersMatched": vals[:8],
                                "context": context.strip()[:420],
                            })
                        for value in vals:
                            numbers[value] = context.strip()
                        if vals:
                            snippets.append({"keyword": match.group(0), "numbers": vals[:10], "context": context.strip()})
                if numbers:
                    return {
                        **base,
                        "numbers": list(numbers.keys())[:40],
                        "snippets": snippets[:24],
                        "extractionDiagnostics": {
                            "method": "OpenDART ZIP",
                            "archiveEntries": len(names),
                            "textFilesParsed": parsed_files,
                            "decodedTextChars": decoded_chars,
                            "keywordHits": keyword_hits,
                        },
                    }
                # A valid ZIP can still contain an empty/poorly decoded main document.
                # Retry the public viewer before treating a zero-value parse as a real zero.
                last_error = (
                    f"OpenDART ZIP parsed but no material numeric contexts matched "
                    f"(entries={len(names)}, textFiles={parsed_files}, chars={decoded_chars}, keywords={keyword_hits})"
                )
                viewer_diag = {"openDartZipEntries": len(names), "openDartTextFilesParsed": parsed_files,
                               "openDartDecodedTextChars": decoded_chars, "openDartKeywordHits": keyword_hits,
                               "openDartKeywordSamples": keyword_samples[:8]}
                viewer_text = fetch_dart_viewer_text(receipt_no, viewer_diag)
                if viewer_text:
                    return extract_viewer_facts(base, viewer_text, last_error, viewer_diag)
                return {
                    **base, "numbers": [], "snippets": [],
                    "fallbackSource": "DART HTML viewer attempted",
                    "viewerFallbackDiagnostics": viewer_diag,
                    "error": last_error,
                }
        except zipfile.BadZipFile:
            # Some OpenDART outages return a branded HTML page (not the documented
            # status-800 XML), so recognize the payload shape before generic parsing.
            is_html_page = raw.lstrip().lower().startswith((b"<!doctype html", b"<html"))
            if is_html_page:
                status,message="html","OpenDART document endpoint returned HTML instead of ZIP"
            else:
                status,message=describe_api_error(raw)
            last_error=f"OpenDART status {status or 'unknown'}: {message}"
            # A service-wide maintenance/HTML block should trip the circuit breaker.
            # Fall back to the public DART viewer immediately rather than retrying
            # the same non-ZIP response for every receipt.
            if status.lower()=="html" or status=="800" or re.search(r"시스템\s*점검|maintenance|temporarily unavailable",message,re.I):
                OPENDART_MAINTENANCE_SEEN = True
                break
            break
        except Exception as exc:
            last_error=f"OpenDART response parse failed: {type(exc).__name__}: {exc}"
            break
    if re.search(r"status\s*(?:800|014)|returned HTML|HTML instead of ZIP|Expected ZIP but received|파일이\s*존재하지\s*않습니다|no material numeric contexts matched|시스템\s*점검|maintenance|temporarily unavailable|timed?\s*out|urlerror|connection reset", last_error, re.I):
        viewer_diag = {}
        viewer_text = fetch_dart_viewer_text(receipt_no, viewer_diag)
        if viewer_text:
            return extract_viewer_facts(base, viewer_text, last_error, viewer_diag)
        return {**base, "numbers": [], "snippets": [], "fallbackSource": "DART HTML viewer attempted", "viewerFallbackDiagnostics": viewer_diag, "error": last_error}
    return {**base, "numbers": [], "snippets": [], "error": last_error}

def main():
    if not IN.exists():
        OUT.write_text(json.dumps({"count": 0, "items": [], "errors": ["dart.json missing"]}, ensure_ascii=False), encoding="utf-8")
        return
    payload = json.loads(IN.read_text(encoding="utf-8"))
    rows = payload.get("items", []) if isinstance(payload, dict) else []
    # OpenDART maintenance must not erase a successful extraction for the same receipt.
    prior_payload = {}
    try:
        if OUT.exists():
            prior_payload = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        prior_payload = {}
    prior_by_receipt = {
        str(x.get("receiptNo")): x
        for x in prior_payload.get("items", [])
        if x.get("receiptNo")
    } if isinstance(prior_payload, dict) else {}
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
    for row in results:
        previous = prior_by_receipt.get(str(row.get("receiptNo") or ""))
        error = str(row.get("error") or "")
        temporary = bool(
            re.search(r"status\s*(?:800|014)|파일이\s*존재하지\s*않습니다|시스템\s*점검|maintenance|temporarily unavailable|timed?\s*out|urlerror|connection reset|no material numeric contexts matched", error, re.I)
            or (not row.get("numbers") and row.get("viewerFallbackDiagnostics"))
        )
        if temporary and previous and previous.get("numbers"):
            row["numbers"] = previous.get("numbers", [])
            row["snippets"] = previous.get("snippets", [])
            row["cacheFallback"] = True
            row["cacheSourceGeneratedAt"] = prior_payload.get("generatedAt", "")
    with_numbers = [x for x in results if x.get("numbers")]
    cache_fallbacks = sum(1 for x in results if x.get("cacheFallback"))
    OUT.write_text(json.dumps({"count": len(results), "items": results}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"DART numeric extraction: {len(with_numbers)} docs with material numeric signals / {len(results)} docs inspected; reused prior values for {cache_fallbacks}")

if __name__ == "__main__":
    main()
