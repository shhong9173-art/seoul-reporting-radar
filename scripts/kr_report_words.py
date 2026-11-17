#!/usr/bin/env python3
"""보고서 전체 새 낱말(11-17 기자 '그렇게해').

정기보고서 숨은 대목(kr_report_notes.py)은 정해진 대목(보고기간 후 사건·제재·소송·연결 범위·이행보증·수주 등)만 읽는다.
그 밖의 장(사업의 내용, 주석의 아무 데나)에 새로 적힌 줄은 놓친다. 그래서 정기보고서 원문 미리 넣기(dart_text_prewarm.py)가
기자 전용 저장소에 넣어 둔 이번·앞 보고서 글자를 저장소 안에서 줄 단위로 비교해(/ingest/dart-text-scan), 앞 보고서에 없던 줄 가운데
감시 낱말(회생·가압류·영업정지·철수·매각·과징금 등)이 든 줄만 받아 정기보고서 감시 결과(kr-report-notes)에 '보고서 전체 새 낱말'로 붙인다.

- 회사·보고서마다 한 번만(같은 접수번호를 다시 비교하지 않는다). 이번·앞 보고서 글자가 아직 저장소에 없으면 다음 실행.
- 문장 비교는 숫자·기호·띄어쓰기를 뺀 글자 기준(금액·날짜만 바뀐 문장은 같은 문장) — 서식이 바뀌면 옛 문장이 새 문장으로 보일 수 있다.
- 11-17 첫 실행(줄 단위)이 일반 조항·회계정책·옛 일 문단을 많이 냈다 — 이번 보고 기간 표시(당분기 중·보고기간 후·앞 보고서 기준일 뒤 날짜)가
  있는 문장(앞으로의 날짜·'예정입니다'·'진행 중입니다' 포함)만 남기고, '…할 수 있습니다'·'경우'·정책·기준서 같은 일반 조항 문장은 뺀다.
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

import kr_exec_watch as kx  # noqa: E402  (BASE)
import kr_report_notes as rn  # noqa: E402  (MONTH·in_period)
import private_store as ps  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
KIND = "보고서 전체 새 낱말"
# 무거운 순서(화면에도 이 순서로) — 11-17 추천 목록: 회생·가압류·영업정지·철수·매각·과징금 + 같은 갈래 낱말
WORDS = ["회생", "파산", "영업정지", "조업정지", "가동중단", "가동 중단", "생산중단", "생산 중단", "압수수색", "가압류", "가처분",
         "고발", "과징금", "철수", "청산", "매각", "리콜"]
KEEP = 8
SCAN_MAX = 120
VERSION = 4   # 4(11-18): 출입처 외 표시 · 2(11-17): 문장 단위 비교 + 이번 보고 기간 표시가 있는 문장만 + 일반 조항 문장 빼기 · 3: 불확실성 문구·법령 시행 목록·배출권·표 머리 문장도 뺌
# 이번 보고 기간에 일어난 일이라는 표시(날짜는 rn.in_period로 따로 본다)
NOW_MARK = re.compile(r"당분기\s*(중|말|에)|당기\s*중|보고기간\s*(후|종료일\s*이후|말\s*이후)|작성기준일\s*이후|(진행|추진|검토|협의)\s*중(입니다|이며|에\s*있)|예정(입니다|이며)")
# 일반 조항·회계정책·계약 조건 문장(11-17 첫 실행: '…과징금을 부과 받을 수 있습니다', '매각예정으로 분류된 …의 처분', '풋옵션 … 매각할 수 있습니다')
# 3판(11-17 2판 실행 38곳): '…과징금 또는 벌금 등이 … 합리적으로 추정할 수 없어 충당부채를 인식하지 아니하였습니다'(LG화학·HD현대오일뱅크),
# 법령 시행 목록(KG모빌리티 '…과징금/과태료 제재(시행-2025.8.14)'), 배출권 매각, '…내역은 다음과 같습니다' 표 머리, 사채·주주간 약정의 '…경우' 조건
BOILER = re.compile(r"수\s*있(습니다|다|으며|는)|경우|정책|기준서|조건으로|의거|에 따라\s*(정한|부과)|해당하는\s*행위|합리적으로\s*(추정|예측)할\s*수\s*없"
                    r"|(공포|시행)\s*[-–(/]|배출권|다음과\s*같습니다")


# 출입처 외(11-18 '추천대로'): 정기보고서 감시와 같은 NON_BEAT 이름, 그리고 '종속회사인 (주)○○'처럼 이름이 적힌 국내 자회사 —
# 줄 앞에 〔출입처 외 ○○〕를 붙이고 뒤로 보낸다(GS 보고서의 GS E&R 해남풍력 매각, 포스코홀딩스 보고서의 포스코이앤씨 영업정지 등).
# 해외 법인 이름(…Co., Ltd.·LLC)은 그 회사 자신의 일로 보고 붙이지 않는다(LG화학 하이퐁 법인 청산 등).
SUB = re.compile(r"(?:종속(?:회사|기업)|자회사)(?:인|의)?\s*(?:\(주\)|㈜|주식회사)?\s*([가-힣][가-힣A-Za-z0-9]{1,15})")
PARTICLE = re.compile(r"(?:\(주\)|㈜)?(?:은|는|이|가|의|에|와|과|를|을|로|으로)?$")


def outsider(line, company):
    for n in rn.NON_BEAT:
        if n in line:
            return n
    m = SUB.search(line)
    if m:
        name = PARTICLE.sub("", m.group(1)).strip()
        if len(name) >= 2 and name not in (company, "주식회사") and not company.startswith(name):
            return name
    return None


def letters(s):
    return re.sub(r"[^가-힣A-Za-z]", "", str(s or ""))


def run(doc, token, *, post, now=None):
    """(바뀐 문서, 건수). doc은 기자 전용 저장소의 kr-report-notes 문서(그대로 고쳐서 돌려준다)."""
    now = now or dt.datetime.now(KST)
    stamp = now.isoformat(timespec="seconds")
    period = f"{(doc.get('period') or {}).get('year')}{(doc.get('period') or {}).get('report')}"
    label = (doc.get("period") or {}).get("label") or ""
    year, report = (doc.get("period") or {}).get("year"), str((doc.get("period") or {}).get("report") or "")
    dy, base_report = kx.BASE.get(report, (0, report))
    since_month = (int(year or now.year) + dy, int(rn.MONTH.get(base_report, "01")))
    events = [e for e in doc.get("events") or [] if isinstance(e, dict)]
    counts = {"eligible": 0, "already": 0, "scanned": 0, "missing": 0, "failed": 0, "events": 0, "lines": 0}
    headers = ps._headers(token)
    fresh = []
    stale = set()
    for short, v in (doc.get("companies") or {}).items():
        if not (isinstance(v, dict) and v.get("status") == "ok" and v.get("period") == period
                and re.fullmatch(r"\d{14}", str(v.get("rcept") or "")) and re.fullmatch(r"\d{14}", str(v.get("baseRcept") or ""))):
            continue
        counts["eligible"] += 1
        if (v.get("wordScan") or {}).get("rcept") == v["rcept"] and (v.get("wordScan") or {}).get("v") == VERSION:
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
        got = [x for x in body.get("lines") or [] if isinstance(x, dict) and x.get("word") in WORDS and letters(x.get("line"))[:40] not in known
               and (NOW_MARK.search(str(x.get("line"))) or rn.in_period(str(x.get("line")), since_month, (9999, 12))) and not BOILER.search(str(x.get("line")))]
        for x in got:
            x["who"] = outsider(str(x.get("line")), short)
        got.sort(key=lambda x: (1 if x["who"] else 0, WORDS.index(x["word"])))
        stale.add(f"rptword:{v['rcept']}")   # 다시 비교한 보고서는 앞 판의 줄을 지운다(0줄이면 그대로 없어진다)
        v["wordScan"] = {"v": VERSION, "rcept": v["rcept"], "base": v["baseRcept"], "at": stamp, "lines": len(got), "raw": len(body.get("lines") or [])}
        counts["scanned"] += 1
        if not got:
            continue
        lines = [f"{'〔출입처 외 ' + x['who'] + '〕 ' if x['who'] else ''}〔{x['word']}〕 {str(x['line'])[:600]}" for x in got[:KEEP]] + ([f"… 그 밖 {len(got) - KEEP}줄"] if len(got) > KEEP else [])
        try:
            age = (now.date() - dt.datetime.strptime(str(v.get("filed")), "%Y%m%d").date()).days
        except ValueError:
            age = 0
        words = list(dict.fromkeys(x["word"] for x in got))
        fresh.append({"id": f"rptword:{v['rcept']}", "kind": KIND, "company": short, "tier": "B", "url": v.get("url") or f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={v['rcept']}",
                      "detectedAt": stamp, "filed": v.get("filed"), "period": label, "lines": lines, **({"late": True} if age >= 2 else {}),
                      "text": f"{short} {label} 보고서 전체에서 앞 보고서에 없던 줄 가운데 {'·'.join(words[:5])} 낱말이 든 줄 {len(got)}개 — {str(got[0]['line'])[:200]}"})
        counts["lines"] += len(got)
    ids = {e["id"] for e in fresh} | stale
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
