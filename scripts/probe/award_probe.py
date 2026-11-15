"""probe 251: (가) 이미 보도된 건(한화시마론 매각, 11-13 이데일리)이 분기보고서의 어느 대목에 적혔는지 — 대목 제목과 앞뒤 글.
(나) 중국 SAMR 간이사건 공시 목록 API, 인도 CCI 심사 중 신고 목록의 자료 주소. 공개 페이지만, 저장 안 함."""
import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
OUT = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36", "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,ko;q=0.7"}
TITLE = re.compile(r"<TITLE\b[^>]*>(.*?)</TITLE>", re.S | re.I)
plain = lambda t: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))


def part_a():
    key = os.environ.get("DART_API_KEY")
    if not key:
        OUT.append("[가] DART_API_KEY 없음")
        return
    r = requests.get("https://opendart.fss.or.kr/api/document.xml", params={"crtfc_key": key, "rcept_no": "20261112000489"}, timeout=180)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    OUT.append(f"[가] 한화솔루션 3분기보고서 zip 파일 {len(z.namelist())}개 · {len(r.content)}바이트")
    for name in z.namelist():
        raw = z.read(name)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("cp949", "replace")
        hits = [m.start() for m in re.finditer("시마론|Cimarron", text)]
        if not hits:
            continue
        marks = [(m.start(), plain(m.group(1))) for m in TITLE.finditer(text)]
        seen = {}
        for h in hits:
            title = next((t for pos, t in reversed(marks) if pos < h), "?")
            seen.setdefault(title, []).append(h)
        OUT.append(f"   파일 {name} · {len(text)}자 · '시마론' {len(hits)}곳 · 대목 {len(seen)}개")
        for title, pos in list(seen.items())[:12]:
            ctx = plain(text[max(0, pos[0] - 260):pos[0] + 320])
            OUT.append(f"   · 대목 「{title[:60]}」 {len(pos)}곳: {ctx[:520]}")


def part_b():
    q = {"parseType": "bulidstatic", "webId": "29e9522dc89d4e088a953d8cede72f4c", "tplSetId": "5c30fb89ae5e48b9aefe3cdf49853830", "pageType": "column",
         "tagId": "ajax分页", "editType": "null", "pageId": "52e2e352f3b84eeaa3e010400866831d"}
    try:
        r = requests.get("https://www.samr.gov.cn/api-gateway/jpaas-publish-server/front/page/build/unit", params=q, headers={**UA, "Referer": "https://www.samr.gov.cn/fldes/ajgs/jyaj/"}, timeout=40)
        OUT.append(f"[SAMR 목록 API] HTTP {r.status_code} · {len(r.text)}자 · {r.headers.get('content-type')}")
        try:
            body = r.json()
            OUT.append(f"   JSON 키 {list(body)[:8]} · data 키 {list((body.get('data') or {}))[:8] if isinstance(body.get('data'), dict) else type(body.get('data')).__name__}")
            html = (body.get("data") or {}).get("html") if isinstance(body.get("data"), dict) else str(body.get("data") or "")
        except ValueError:
            html = r.text
        rows = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html or "", re.S)
        items = [(h, plain(t)) for h, t in rows if "案" in plain(t) or "公示" in plain(t)]
        dates = re.findall(r"20\d\d-\d\d-\d\d", html or "")
        OUT.append(f"   링크 {len(rows)}개 · 사건 줄 {len(items)}개 · 날짜 {dates[:3]}…{dates[-2:]} · 쪽 넘김 낱말 {re.findall(r'pageNo|pageSize|totalPage|pageCount|nextPage', html or '')[:6]}")
        for h, t in items[:6]:
            OUT.append(f"   · {t[:90]} | {h[:90]}")
        kr = [t for _, t in items if re.search(r"现代|起亚|浦项|韩华|LG|SK|晓星|乐天|斗山|锦湖|韩泰|高丽亚铅|东国|世亚|LS|大韩电线|三星|韩国", t)]
        OUT.append(f"   한국 기업 낱말 든 줄 {len(kr)}개: " + " / ".join(x[:80] for x in kr[:6]))
        if items:
            u = items[0][0]
            u = u if u.startswith("http") else "https://www.samr.gov.cn" + u
            d = requests.get(u, headers=UA, timeout=40)
            OUT.append(f"   첫 사건 글 HTTP {d.status_code} · {len(d.text)}자 · 첨부 {re.findall(r'href=\"([^\"]+\.(?:pdf|docx?|xlsx?))\"', d.text)[:3]} · 본문 「{plain(re.sub(r'<(script|style).*?</\\1>', ' ', d.text, flags=re.S))[300:700]}」")
    except Exception as e:  # noqa: BLE001
        OUT.append(f"[SAMR 목록 API] 실패 {type(e).__name__}: {str(e)[:150]}")
    try:
        r = requests.get("https://www.cci.gov.in/combination/notice-under-review", headers=UA, timeout=40)
        b = r.text
        OUT.append(f"[CCI 심사 중 신고] HTTP {r.status_code} · {len(b)}자")
        for m in list(re.finditer(r"datatable_ajax|ajax\s*:", b))[:4]:
            OUT.append("   · " + re.sub(r"\s+", " ", b[max(0, m.start() - 200):m.start() + 500]))
        for m in list(re.finditer(r"<th[^>]*>(.*?)</th>", b, re.S))[:12]:
            OUT.append("   th: " + plain(m.group(1))[:40])
    except Exception as e:  # noqa: BLE001
        OUT.append(f"[CCI] 실패 {type(e).__name__}: {str(e)[:150]}")


for f in (part_a, part_b):
    try:
        f()
    except Exception as e:  # noqa: BLE001
        OUT.append(f"[{f.__name__}] 예외 {type(e).__name__}: {str(e)[:200]}")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
