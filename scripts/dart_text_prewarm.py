#!/usr/bin/env python3
"""출입처 정기보고서 원문 글자 미리 넣기(11-17 기자 '추천대로').

dart_find_text(커넥터)는 Cloudflare 작업자에서 OpenDART 원문(ZIP)을 받는데, 큰 분기보고서는 15초 안에 안 와 '시간 초과'가 잦았고,
DART 누리집 장별 나눠 읽기는 호출당 바깥 요청 50개 한도에 걸려 한 보고서를 세 번에 나눠 읽어야 했다(11-17 LG화학 3분기보고서 96개 장).
GitHub Actions에서는 같은 ZIP이 받아진다(정기보고서 감시가 매일 받는다). 그래서 정기보고서 감시가 읽은 출입처 보고서(이번 기간)의 원문을
여기서 받아 글자로 바꿔 기자 전용 저장소(/ingest/dart-text)에 넣는다. 그 뒤 dart_find_text는 저장소 안에서 한 번에 끝까지 찾는다.

- 대상: 기자 전용 저장소의 정기보고서 감시 결과(kr-report-notes)에서 이번 기간 'ok'로 읽은 회사의 접수번호와 그 앞 보고서 접수번호.
  이미 넣은 접수번호는 건너뛴다.
- 한 실행에 BUDGET건(원문 1개 20초 안팎, 20건이면 7분 안팎). 넘으면 다음 실행.
- 공개 공시 글이지만 로그에는 건수만 적는다(회사 이름·글자를 찍지 않는다).
- 글자 바꾸기는 작업자(common.mjs htmlToText)와 같은 규칙에 DART 표 칸(TE·TU)을 더한 것.
"""
from __future__ import annotations

import argparse
import html
import io
import json
import os
import re
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import private_store as ps  # noqa: E402

API = "https://opendart.fss.or.kr/api"
HEADERS = {"User-Agent": "Mozilla/5.0 (seoul-reporting-radar)", "Accept": "application/json"}
SCHEMA = "dart_text/v1"
BUDGET = 20
DOC_TIMEOUT = 150
PAUSE = 0.5


def html_to_text(s):
    """작업자 htmlToText와 같은 규칙(+ DART XML 표 칸 TE·TU)."""
    s = re.sub(r"<!--[\s\S]*?-->", " ", s)
    s = re.sub(r"<(script|style|noscript|svg)[\s\S]*?</\1>", " ", s, flags=re.I)
    s = re.sub(r"<\s*(br|/p|/div|/tr|/li|/h\d|/table|/title)\b[^>]*>", "\n", s, flags=re.I)
    s = re.sub(r"</t[dheu]>", " | ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t ]+", " ", s)
    s = re.sub(r" *\n[ \n]*", "\n", s)
    return s.strip()


def decode(raw):
    for enc in ("utf-8", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def fetch_files(key, rcp, *, get):
    """(파일들 [{name, text}], 오류). OpenDART 014(파일 준비 전)는 오류로 돌려 다음 실행에 다시."""
    try:
        r = get(f"{API}/document.xml", params={"crtfc_key": key, "rcept_no": rcp}, headers=HEADERS, timeout=DOC_TIMEOUT)
    except Exception as e:  # noqa: BLE001 — 조회 실패는 다음 실행
        return None, f"{type(e).__name__}"
    body = getattr(r, "content", b"") or b""
    if not body.startswith(b"PK"):
        return None, "014" if b"<status>014" in body[:300] else "not-zip"
    try:
        z = zipfile.ZipFile(io.BytesIO(body))
        files = []
        for n in sorted(z.namelist(), key=lambda n: z.getinfo(n).file_size, reverse=True):
            text = html_to_text(decode(z.read(n)))
            if text:
                files.append({"name": n, "text": text})
        return (files or None), (None if files else "empty")
    except (zipfile.BadZipFile, OSError, ValueError) as e:
        return None, type(e).__name__


def targets(notes_doc):
    """정기보고서 감시가 이번 기간 'ok'로 읽은 회사의 접수번호(중복 없이) — 이번 보고서 먼저, 그다음 앞 보고서(baseRcept).
    11-17: 보고서 전체 새 낱말 감시(kr_report_words.py)가 이번·앞 보고서 줄을 저장소 안에서 비교한다."""
    period = f"{(notes_doc.get('period') or {}).get('year')}{(notes_doc.get('period') or {}).get('report')}"
    ok = [v for v in (notes_doc.get("companies") or {}).values()
          if isinstance(v, dict) and v.get("status") == "ok" and v.get("period") == period and re.fullmatch(r"\d{14}", str(v.get("rcept") or ""))]
    out = []
    for r in [v["rcept"] for v in ok] + [str(v.get("baseRcept") or "") for v in ok]:
        if re.fullmatch(r"\d{14}", r) and r not in out:
            out.append(r)
    return out


def run(key, token, *, get, post, sleep=time.sleep, budget=BUDGET, notes_doc=None):
    rcpts = targets(notes_doc or {})
    counts = {"targets": len(rcpts), "had": 0, "put": 0, "waiting": 0, "failed": 0, "left": 0, "chars": 0}
    headers = ps._headers(token)
    for rcp in rcpts:
        try:
            h = get(f"{ps.WORKER}/ingest/dart-text", params={"rcp": rcp}, headers=headers, timeout=30)
            if getattr(h, "status_code", 0) == 200 and (h.json() or {}).get("have"):
                counts["had"] += 1
                continue
        except Exception:  # noqa: BLE001 — 있는지 모르면 넣어 본다(덮어쓰기)
            pass
        if budget <= 0:
            counts["left"] += 1
            continue
        budget -= 1
        files, err = fetch_files(key, rcp, get=get)
        sleep(PAUSE)
        if not files:
            counts["waiting" if err == "014" else "failed"] += 1
            continue
        try:
            r = post(f"{ps.WORKER}/ingest/dart-text", data=json.dumps({"schema": SCHEMA, "rcp": rcp, "files": files}, ensure_ascii=False).encode("utf-8"),
                     headers=headers, timeout=120)
            ok = getattr(r, "status_code", 0) == 200
        except Exception:  # noqa: BLE001
            ok = False
        if ok:
            counts["put"] += 1
            counts["chars"] += sum(len(f["text"]) for f in files)
        else:
            counts["failed"] += 1
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=BUDGET)
    a = ap.parse_args()
    key, token = os.environ.get("DART_API_KEY"), os.environ.get("MCP_ACCESS_TOKEN")
    if not key or not token:
        print("::notice title=dart-text-prewarm::DART_API_KEY 또는 MCP_ACCESS_TOKEN 없음 — 건너뜀")
        return 0
    import requests
    try:
        notes_doc = ps.get("kr-report-notes", token)
    except Exception as e:  # noqa: BLE001
        print(f"::notice title=dart-text-prewarm::정기보고서 감시 저장본 읽기 실패 {type(e).__name__} — 건너뜀")
        return 0
    c = run(key, token, get=requests.get, post=requests.post, budget=a.budget, notes_doc=notes_doc)
    # 공개 로그에는 건수만
    print(f"::notice title=dart-text-prewarm::대상 보고서 {c['targets']} · 이미 있음 {c['had']} · 이번에 넣음 {c['put']}(글자 {c['chars']}) · "
          f"파일 준비 전 {c['waiting']} · 실패 {c['failed']} · 다음 실행으로 {c['left']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
