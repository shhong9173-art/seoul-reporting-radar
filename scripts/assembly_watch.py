"""국회 법안 감시: 열린국회정보 '국회의원 발의법률안'(nzmimeepazxkubdpn) 중 출입 업종 법안 → 기자 전용 저장소.

- 22대 발의 법안을 최신순으로 최근 14일치 읽는다(쪽당 100건, 최대 8쪽). 법안 이름으로만 고른다:
  core(자동차관리법·철강산업 특별법·전기사업법·전력망·관세법 등)는 B, 관련 낱말(자동차·전력·화학 등)은 C.
- 이미 잡은 법안은 의안ID로 다시 조회해 단계(소관위 회부·상정·처리, 법사위, 본회의)가 바뀌면 이벤트로 남긴다.
- 첫 실행은 기준선(이벤트 없음). 조회 실패는 0건이 아니라 미확인. 공개 로그는 건수만, 인증키는 저장하지 않는다.
- 법안 발의·처리는 공개 의정 정보다. 단독 근거가 아니고, 내용(제안이유)은 의안 원문에서 확인한다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "assembly_bills/v1"
CONFIG = ROOT / "data" / "assembly_bills.json"
URL = "https://open.assembly.go.kr/portal/openapi/nzmimeepazxkubdpn"
SERVICE = "nzmimeepazxkubdpn"
EVENT_KEEP_DAYS = 120
# (field, label) in pipeline order; the furthest filled step is the bill's stage.
STAGES = [("COMMITTEE_DT", "소관위 회부"), ("CMT_PRESENT_DT", "소관위 상정"), ("CMT_PROC_DT", "소관위 처리"),
          ("LAW_SUBMIT_DT", "법사위 회부"), ("LAW_PRESENT_DT", "법사위 상정"), ("LAW_PROC_DT", "법사위 처리"),
          ("PROC_DT", "본회의 의결")]


def now_kst():
    return dt.datetime.now(KST)


class ApiError(RuntimeError):
    pass


def call(params, key, *, get=None):
    """One page. Returns (rows, total). INFO-200 (no data) is an empty page, any other code raises."""
    if get is None:
        import requests
        get = requests.get
    try:
        r = get(URL, params={"KEY": key, "Type": "json", **params}, timeout=40)
    except Exception as e:  # never the URL (it carries the key)
        raise ApiError(type(e).__name__)
    if r.status_code != 200:
        raise ApiError(f"HTTP {r.status_code}")
    try:
        j = r.json()
    except ValueError:
        raise ApiError("JSON 아님")
    if isinstance(j, dict) and "RESULT" in j and SERVICE not in j:
        code = str((j["RESULT"] or {}).get("CODE") or "")
        if code == "INFO-200":
            return [], 0
        raise ApiError(f"코드 {code[:20]}")
    block = j.get(SERVICE) if isinstance(j, dict) else None
    if not isinstance(block, list) or not block:
        raise ApiError("응답 형식 변경")
    head = block[0].get("head") or []
    total = next((h.get("list_total_count") for h in head if isinstance(h, dict) and "list_total_count" in h), None)
    result = next((h.get("RESULT") for h in head if isinstance(h, dict) and "RESULT" in h), {}) or {}
    if str(result.get("CODE", "INFO-000")) != "INFO-000":
        raise ApiError(f"코드 {str(result.get('CODE'))[:20]}")
    rows = (block[1].get("row") if len(block) > 1 and isinstance(block[1], dict) else None) or []
    if not isinstance(rows, list) or not isinstance(total, int):
        raise ApiError("응답 형식 변경")
    return rows, total


def law_of(name):
    base = re.sub(r"\s*\((?:대안|정부)\)\s*$", "", str(name or "").strip())
    base = re.sub(r"\s*(?:일부개정법률안|전부개정법률안|폐지법률안|법률안)$", "", base)
    return re.sub(r"(법)안$", r"\1", base).strip()


def match(name, cfg):
    """(core label or None, matched words) — by bill name only."""
    text = str(name or "")
    for group in cfg["core"]:
        hit = [p for p in group["patterns"] if p in text]
        if hit:
            return group["label"], hit
    if any(x in text for x in cfg.get("exclude", [])):
        return None, []
    words = [k for k in cfg["keywords"] if k in text]
    return None, words


def stage_of(row):
    """(index, label, date): furthest step reached; 0 = 발의(접수)."""
    idx, label, date = 0, "발의", str(row.get("PROPOSE_DT") or "")[:10]
    for i, (field, name) in enumerate(STAGES, start=1):
        v = str(row.get(field) or "").strip()
        if v:
            idx, label, date = i, name, v[:10]
    if idx == len(STAGES) or row.get("PROC_RESULT"):
        result = str(row.get("PROC_RESULT") or "").strip()
        if result:
            label = f"본회의 {result}" if idx == len(STAGES) else result
            idx = max(idx, len(STAGES))
    elif idx == 3 and row.get("CMT_PROC_RESULT_CD"):
        label = f"소관위 처리({row['CMT_PROC_RESULT_CD']})"
    elif idx == 6 and row.get("LAW_PROC_RESULT_CD"):
        label = f"법사위 처리({row['LAW_PROC_RESULT_CD']})"
    return idx, label, date


def record(row, cfg, *, stamp, old=None):
    core, words = match(row.get("BILL_NAME"), cfg)
    idx, label, date = stage_of(row)
    rec = {
        "id": str(row.get("BILL_ID") or ""), "no": str(row.get("BILL_NO") or ""),
        "name": str(row.get("BILL_NAME") or "")[:200], "law": law_of(row.get("BILL_NAME"))[:160],
        "committee": row.get("COMMITTEE") or None, "proposedOn": str(row.get("PROPOSE_DT") or "")[:10],
        "proposer": str(row.get("PROPOSER") or "")[:80], "lead": str(row.get("RST_PROPOSER") or "")[:40],
        "core": core, "matched": words, "stageIndex": idx, "stage": label, "stageAt": date,
        "url": str(row.get("DETAIL_LINK") or "")[:300], "firstSeen": (old or {}).get("firstSeen") or stamp,
        "lastChecked": stamp, "isNew": (old or {}).get("isNew", False),
    }
    return rec


def run(cfg, *, now, previous=None, key="", get=None, sleep=time.sleep):
    stamp = now.isoformat(timespec="seconds")
    prev = previous if isinstance(previous, dict) and previous.get("schema") == SCHEMA else None
    baseline = not (prev or {}).get("baselineSince")
    bills = {b["id"]: b for b in (prev or {}).get("bills", []) if isinstance(b, dict) and b.get("id")}
    events = [e for e in (prev or {}).get("events", []) if isinstance(e, dict)
              and str(e.get("detectedAt", "")) >= (now - dt.timedelta(days=EVENT_KEEP_DAYS)).isoformat()]
    have = {e.get("id") for e in events}
    checks = []
    if not key:
        checks.append({"source": "열린국회정보 발의법률안", "status": "unset", "error": "ASSEMBLY_API_KEY 없음"})
        return _doc(cfg, prev, stamp, checks, bills, events, ok=False)

    def note(ev):
        if ev["id"] not in have:
            have.add(ev["id"])
            events.append(ev)

    def update(row):
        bid = str(row.get("BILL_ID") or "")
        old = bills.get(bid)
        rec = record(row, cfg, stamp=stamp, old=old)
        if not old:
            rec["isNew"] = not baseline
            if rec["isNew"]:
                note({"id": f"bill:{bid}:발의", "billId": bid, "kind": "발의", "detectedAt": stamp, "date": rec["proposedOn"],
                      "core": rec["core"], "law": rec["law"], "lead": rec["lead"]})
        elif rec["stageIndex"] > old.get("stageIndex", 0) or (rec["stage"] != old.get("stage") and rec["stageIndex"] >= len(STAGES)):
            note({"id": f"bill:{bid}:{rec['stage']}", "billId": bid, "kind": rec["stage"], "detectedAt": stamp,
                  "date": rec["stageAt"], "core": rec["core"], "law": rec["law"], "lead": rec["lead"],
                  "from": old.get("stage")})
        bills[bid] = rec

    # 1) Newest bills (the API returns BILL_NO descending) until older than the lookback.
    since = (now.date() - dt.timedelta(days=int(cfg.get("lookbackDays", 14)))).isoformat()
    listed = kept = pages = 0
    total = None
    try:
        for page in range(1, int(cfg.get("maxPages", 8)) + 1):
            rows, total = call({"pIndex": page, "pSize": 100, "AGE": cfg["age"]}, key, get=get)
            pages += 1
            listed += len(rows)
            for row in rows:
                core, words = match(row.get("BILL_NAME"), cfg)
                if (core or words) and str(row.get("PROPOSE_DT") or "") >= since:
                    kept += 1
                    update(row)
            dates = [str(r.get("PROPOSE_DT") or "") for r in rows if r.get("PROPOSE_DT")]
            if not rows or (dates and min(dates) < since):
                break
            sleep(0.3)
        else:
            checks.append({"source": "열린국회정보 발의법률안", "status": "partial", "error": f"{pages}쪽 한도 — 조회 기간 끝까지 못 읽음",
                           "pages": pages, "listed": listed, "kept": kept, "total": total})
        if not checks:
            checks.append({"source": "열린국회정보 발의법률안", "status": "ok", "pages": pages, "listed": listed, "kept": kept, "total": total})
    except ApiError as e:
        checks.append({"source": "열린국회정보 발의법률안", "status": "failed", "error": str(e), "pages": pages, "listed": listed})

    # 2) Re-check tracked bills not yet decided (core first, least recently checked first).
    track_from = (now.date() - dt.timedelta(days=int(cfg.get("trackDays", 365)))).isoformat()
    todo = [b for b in bills.values() if b.get("stageIndex", 0) < len(STAGES) and b.get("proposedOn", "") >= track_from
            and b.get("lastChecked") != stamp]
    todo.sort(key=lambda b: (b.get("core") is None, b.get("lastChecked") or ""))
    budget = int(cfg.get("recheckPerRun", 60))
    done = failed = 0
    err = None
    if checks[0]["status"] != "failed":
        for b in todo[:budget]:
            try:
                rows, _ = call({"pIndex": 1, "pSize": 1, "AGE": cfg["age"], "BILL_ID": b["id"]}, key, get=get)
            except ApiError as e:
                failed += 1
                err = str(e)
                if failed >= 3:
                    break
                continue
            done += 1
            if rows:
                update(rows[0])
            else:
                b["lastChecked"] = stamp
            sleep(0.2)
    check = {"source": "열린국회정보 단계 재확인", "status": "ok" if not failed else "partial", "checked": done,
             "pending": max(0, len(todo) - done - failed), "tracked": len(todo)}
    if err:
        check["error"] = err
    checks.append(check)
    ok = checks[0]["status"] in ("ok", "partial")
    return _doc(cfg, prev, stamp, checks, bills, events, ok=ok, now=now)


def _doc(cfg, prev, stamp, checks, bills, events, *, ok, now=None):
    keep_from = ((now or dt.datetime.now(KST)).date() - dt.timedelta(days=int(cfg.get("trackDays", 365)))).isoformat()
    rows = sorted((b for b in bills.values() if b.get("proposedOn", "") >= keep_from),
                  key=lambda b: (b.get("proposedOn", ""), b.get("no", "")), reverse=True)
    events.sort(key=lambda e: (e.get("detectedAt", ""), e.get("id", "")), reverse=True)
    failed = [c for c in checks if c["status"] not in ("ok", "unset")]
    return {"schema": SCHEMA, "generatedAt": stamp,
            "status": "unset" if all(c["status"] == "unset" for c in checks) else ("partial" if failed else "complete"),
            "baselineSince": (prev or {}).get("baselineSince") or (stamp if ok else None),
            "checks": checks, "bills": rows[:1500], "events": events[:600],
            "rules": ["국회의원 발의법률안(열린국회정보)이다. 정부 제출 법안·위원장 대안은 이 목록에 없을 수 있다.",
                      "법안 이름으로만 골랐다. 출입처 영향·내용(제안이유)은 의안 원문(상세 링크)에서 확인한다.",
                      "발의는 입법 시작일 뿐 통과가 아니다. '대안반영폐기'는 위원장 대안에 합쳐졌다는 뜻이다.",
                      "조회 실패는 0건이 아니라 미확인."],
            "confirmedScoops": 0}


def main():
    argparse.ArgumentParser(description="국회 법안 감시(기자 전용 저장소로)").parse_args()
    now = now_kst()
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    import private_store
    previous = None
    if token:
        try:
            previous = private_store.get("assembly-bills", token)
        except private_store.StoreError as e:
            print(f"::warning title=assembly-state::이전 상태 조회 실패({e}) — 저장하지 않고 끝냄(기준선 재설정 방지)")
            sys.exit(1)
    if private_store.late_scheduled_duplicate(previous, now):
        return
    doc = run(cfg, now=now, previous=previous, key=os.environ.get("ASSEMBLY_API_KEY", "").strip())
    lst, rec = doc["checks"][0], doc["checks"][-1]
    fresh = [e for e in doc["events"] if e["detectedAt"] == doc["generatedAt"]]
    print(f"::notice title=assembly-bills::목록 {lst['status']} {lst.get('pages', 0)}쪽·{lst.get('listed', 0)}건 중 업종 {lst.get('kept', 0)}건 · "
          f"단계 재확인 {rec.get('checked', 0)}/{rec.get('tracked', 0)} · 새 이벤트 {len(fresh)}(core {sum(1 for e in fresh if e.get('core'))})")
    if lst.get("error"):
        print(f"::notice title=assembly-errors::{lst['error'][:200]}")
    if not token:
        print("::warning title=assembly-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if lst["status"] == "failed" and previous:
        sys.exit("목록 조회 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("assembly-bills", doc, token)
    print(f"::notice title=assembly-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
