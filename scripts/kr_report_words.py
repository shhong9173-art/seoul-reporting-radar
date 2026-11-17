#!/usr/bin/env python3
"""보고서 전체 새 낱말(11-17 기자 '그렇게해').

정기보고서 숨은 대목(kr_report_notes.py)은 정해진 대목(보고기간 후 사건·제재·소송·연결 범위·이행보증·수주 등)만 읽는다.
그 밖의 장(사업의 내용, 주석의 아무 데나)에 새로 적힌 줄은 놓친다. 그래서 정기보고서 원문 미리 넣기(dart_text_prewarm.py)가
기자 전용 저장소에 넣어 둔 이번·앞 보고서 글자를 저장소 안에서 줄 단위로 비교해(/ingest/dart-text-scan), 앞 보고서에 없던 줄 가운데
감시 낱말(회생·가압류·영업정지·철수·매각·과징금 등)이 든 줄만 받아 정기보고서 감시 결과(kr-report-notes)에 '보고서 전체 새 낱말'로 붙인다.

- 회사·보고서마다 한 번만(같은 접수번호를 다시 비교하지 않는다). 이번·앞 보고서 글자가 아직 저장소에 없으면 다음 실행.
- 줄 비교는 숫자·기호·띄어쓰기를 뺀 글자 기준(금액·날짜만 바뀐 줄은 같은 줄) — 서식이 바뀌면 옛 줄이 새 줄로 보일 수 있다.
- 정기보고서 감시가 이미 새 줄로 잡은 줄은 다시 내지 않는다.
- 등급 B, 즉시 알림은 걸지 않는다(기자가 정하면 건다). 로그에는 건수만.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import private_store as ps  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
KIND = "보고서 전체 새 낱말"
# 무거운 순서(화면에도 이 순서로) — 11-17 추천 목록: 회생·가압류·영업정지·철수·매각·과징금 + 같은 갈래 낱말
WORDS = ["회생", "파산", "영업정지", "조업정지", "가동중단", "가동 중단", "생산중단", "생산 중단", "압수수색", "가압류", "가처분",
         "고발", "과징금", "철수", "청산", "매각", "리콜"]
KEEP = 8
SCAN_MAX = 60


def letters(s):
    return re.sub(r"[^가-힣A-Za-z]", "", str(s or ""))


def run(doc, token, *, post, now=None):
    """(바뀐 문서, 건수). doc은 기자 전용 저장소의 kr-report-notes 문서(그대로 고쳐서 돌려준다)."""
    now = now or dt.datetime.now(KST)
    stamp = now.isoformat(timespec="seconds")
    period = f"{(doc.get('period') or {}).get('year')}{(doc.get('period') or {}).get('report')}"
    label = (doc.get("period") or {}).get("label") or ""
    events = [e for e in doc.get("events") or [] if isinstance(e, dict)]
    counts = {"eligible": 0, "already": 0, "scanned": 0, "missing": 0, "failed": 0, "events": 0, "lines": 0}
    headers = ps._headers(token)
    fresh = []
    for short, v in (doc.get("companies") or {}).items():
        if not (isinstance(v, dict) and v.get("status") == "ok" and v.get("period") == period
                and re.fullmatch(r"\d{14}", str(v.get("rcept") or "")) and re.fullmatch(r"\d{14}", str(v.get("baseRcept") or ""))):
            continue
        counts["eligible"] += 1
        if (v.get("wordScan") or {}).get("rcept") == v["rcept"]:
            counts["already"] += 1
            continue
        try:
            r = post(f"{ps.WORKER}/ingest/dart-text-scan", data=json.dumps({"rcp": v["rcept"], "base": v["baseRcept"], "words": WORDS, "max": SCAN_MAX}),
                     headers=headers, timeout=90)
            body = r.json() if getattr(r, "status_code", 0) == 200 else None
        except Exception:  # noqa: BLE001 — 다음 실행
            body = None
        if not body:
            counts["failed"] += 1
            continue
        if body.get("status") != "ok":
            counts["missing"] += 1
            continue
        # 정기보고서 감시가 이미 새 줄로 잡은 줄은 빼고, 무거운 낱말 순으로
        known = " ".join(letters(l) for e in events if e.get("company") == short and e.get("kind") != KIND for l in e.get("lines") or [])
        got = [x for x in body.get("lines") or [] if isinstance(x, dict) and x.get("word") in WORDS and letters(x.get("line"))[:40] not in known]
        got.sort(key=lambda x: WORDS.index(x["word"]))
        v["wordScan"] = {"rcept": v["rcept"], "base": v["baseRcept"], "at": stamp, "lines": len(got)}
        counts["scanned"] += 1
        if not got:
            continue
        lines = [f"〔{x['word']}〕 {str(x['line'])[:600]}" for x in got[:KEEP]] + ([f"… 그 밖 {len(got) - KEEP}줄"] if len(got) > KEEP else [])
        try:
            age = (now.date() - dt.datetime.strptime(str(v.get("filed")), "%Y%m%d").date()).days
        except ValueError:
            age = 0
        words = list(dict.fromkeys(x["word"] for x in got))
        fresh.append({"id": f"rptword:{v['rcept']}", "kind": KIND, "company": short, "tier": "B", "url": v.get("url") or f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={v['rcept']}",
                      "detectedAt": stamp, "filed": v.get("filed"), "period": label, "lines": lines, **({"late": True} if age >= 2 else {}),
                      "text": f"{short} {label} 보고서 전체에서 앞 보고서에 없던 줄 가운데 {'·'.join(words[:5])} 낱말이 든 줄 {len(got)}개 — {str(got[0]['line'])[:200]}"})
        counts["lines"] += len(got)
    ids = {e["id"] for e in fresh}
    doc["events"] = [e for e in events if e.get("id") not in ids] + fresh
    counts["events"] = len(fresh)
    doc["wordScan"] = {"at": stamp, "words": WORDS, **{k: counts[k] for k in ("eligible", "already", "scanned", "missing", "failed")}}
    return doc, counts


def main():
    token = os.environ.get("MCP_ACCESS_TOKEN")
    if not token:
        print("::notice title=kr-report-words::MCP_ACCESS_TOKEN 없음 — 건너뜀")
        return 0
    import requests
    try:
        doc = ps.get("kr-report-notes", token)
    except Exception as e:  # noqa: BLE001
        print(f"::notice title=kr-report-words::정기보고서 감시 저장본 읽기 실패 {type(e).__name__} — 건너뜀")
        return 0
    if not isinstance(doc, dict) or not doc.get("companies"):
        print("::notice title=kr-report-words::정기보고서 감시 저장본 없음 — 건너뜀")
        return 0
    doc, c = run(doc, token, post=requests.post)
    print(f"::notice title=kr-report-words::비교 대상 {c['eligible']} · 앞서 비교 {c['already']} · 이번 비교 {c['scanned']} · 원문 미리 넣기 전 {c['missing']} · 실패 {c['failed']} · 새 줄 있는 보고서 {c['events']}(줄 {c['lines']})")
    if not c["scanned"]:
        return 0
    status = ps.put("kr-report-notes", doc, token)
    print(f"::notice title=kr-report-words-push::기자 전용 저장소 전송 HTTP {status}")
    return 0 if status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
