"""출입처 공장 굴뚝 측정(가동 신호) 감시 — 한국환경공단 굴뚝 자동측정기기(TMS, CleanSYS) 실시간 측정결과, 기자 전용 저장소 'kr-stacks'.

- 출입처 사업장(data/stack_watch.json 이름 규칙)의 배출구별 최신 측정값(먼지·SOx·NOx 등 중 가장 큰 값)을 실행마다(3시간 간격)
  쌓는다. API는 지금 값만 주므로 이력은 이 감시가 쌓은 것이다.
- 배출구 멈춤 신호: 평소 값(직전 관측 중앙값)이 1 이상이던 배출구가 연달아 STOP_RUNS번 평소의 10% 아래(또는 0.3 아래)로 떨어지면
  '멈춤'. 사업장에서 평소 움직이던 배출구 절반 이상(2개 이상)이 멈추면 A(사업장 가동 중단 신호), 두 곳 이상이거나 큰 배출구면 B.
- 새 배출구 번호·새 사업장(첫 실행 뒤) A — 새 설비 가동 가능성. 목록에서 빠진 배출구(두 번 연속) B. 멈췄던 사업장이 다시 움직이면 B.
- 측정값 0 근처는 설비 정지·정비·측정기 점검·연료 전환일 수 있다. 어느 설비인지(배출구 이름)는 자료에 없다 — 회사 확인.
- 키는 공공데이터 공유 키(DATA_GO_KR_KEY). 키 값은 출력하지 않는다. 조회 실패는 0이 아니라 미확인.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "kr_stacks/v1"
CONFIG = ROOT / "data" / "stack_watch.json"
API = "https://apis.data.go.kr/B552584/cleansys/rltmMesureResult"
POLLUTANTS = ("tsp", "sox", "nox", "hcl", "hf", "nh3", "co")
OBS_KEEP = 24          # 3시간 간격이면 3일치
MIN_OBS = 6            # 평소 값을 정할 최소 관측 수(첫 실행 뒤 하루쯤)
STOP_RUNS = 3          # 연달아 이만큼 낮으면 멈춤(3시간 간격이면 9시간)
MEANINGFUL = 1.0       # 평소 값이 이보다 작으면 멈춤 판단을 하지 않는다(원래 거의 0인 배출구)
LOW_ABS = 0.3
LOW_REL = 0.10
MISSING_RUNS = 2
KEEP_EVENTS_DAYS = 60


class ApiError(RuntimeError):
    pass


def fetch(term, key, *, get=None, sleep=time.sleep):
    """사업장명 포함 검색 한 번(이 API는 한 번에 전체를 준다). 실패는 한 번 더."""
    if get is None:
        import requests
        get = requests.get
    err = None
    for attempt in (0, 1):
        if attempt:
            sleep(3.0)
        try:
            r = get(API, params={"serviceKey": key, "type": "json", "numOfRows": 1000, "pageNo": 1, "factManageNm": term}, timeout=60)
        except Exception as e:  # noqa: BLE001 — class name only
            err = type(e).__name__
            continue
        code = re.search(r'"returnReasonCode"\s*:\s*"?(\d+)', r.text or "")
        if code:
            raise ApiError(f"코드 {code.group(1)}")
        if r.status_code != 200:
            err = f"HTTP {r.status_code}"
            continue
        try:
            d = json.loads(r.text)
        except ValueError:
            err = "비JSON 응답"
            continue
        res = d.get("response") or {}
        rc = str((res.get("header") or {}).get("resultCode") or "")
        if rc not in ("", "0", "00"):
            raise ApiError(f"결과 코드 {rc}")
        items = (res.get("body") or {}).get("items") or []
        items = items.get("item") if isinstance(items, dict) else items
        return items if isinstance(items, list) else ([items] if items else [])
    raise ApiError(err or "응답 없음")


def peak(x):
    """배출구 한 줄의 측정값 중 가장 큰 값(없으면 None)."""
    vals = []
    for p in POLLUTANTS:
        v = x.get(f"{p}_mesure_value")
        try:
            vals.append(float(v))
        except (TypeError, ValueError):
            continue
    return max(vals) if vals else None


def norm(name):
    return re.sub(r"\s+", "", str(name or "").replace("（", "(").replace("）", ")").replace("㈜", "(주)"))


def baseline(obs):
    """멈춤 판단 창(마지막 STOP_RUNS개) 앞의 관측 중앙값. 관측이 모자라면 None."""
    prior = [v for _, v in obs[:-STOP_RUNS] if v is not None]
    return statistics.median(prior) if len(prior) >= MIN_OBS else None


def is_low(v, base):
    return v is not None and v < max(LOW_ABS, base * LOW_REL)


STALE_HOURS = 12


def stack_state(st, now=None):
    """'stopped' | 'running' | 'unknown'(관측 부족·원래 거의 0). 측정 시각이 STALE_HOURS 넘게 그대로면(값이 안 들어옴) 멈춤으로 본다."""
    obs = st.get("obs") or []
    prior = baseline(obs)
    vals = [v for _, v in obs if v is not None]
    base = prior if prior is not None else (statistics.median(vals) if len(vals) >= MIN_OBS else None)
    if base is None or base < MEANINGFUL:
        return "unknown", base
    if now is not None and st.get("lastDt"):
        try:
            age = (now - dt.datetime.strptime(st["lastDt"], "%Y-%m-%d %H:%M").replace(tzinfo=KST)).total_seconds() / 3600
            if age > STALE_HOURS:
                return "stopped", base
        except ValueError:
            pass
    last = [v for _, v in obs[-STOP_RUNS:]]
    if prior is not None and len(last) == STOP_RUNS and all(is_low(v, base) for v in last):
        return "stopped", base
    if last and last[-1] is not None and not is_low(last[-1], base):
        return "running", base
    return "unknown", base


def run(cfg, *, now, previous=None, key, get=None, sleep=time.sleep):
    stamp = now.isoformat(timespec="seconds")
    prev = previous if isinstance(previous, dict) else {}
    first = not prev.get("sites")
    sites = {s["id"]: s for s in prev.get("sites") or [] if isinstance(s, dict) and s.get("id")}
    keep_from = (now - dt.timedelta(days=KEEP_EVENTS_DAYS)).isoformat()
    events = [e for e in prev.get("events") or [] if isinstance(e, dict) and e.get("detectedAt", "") >= keep_from]
    known = {e["id"] for e in events}
    fresh, errors, ok_terms, seen_sites = [], [], 0, set()
    day = now.date().isoformat()

    def emit(eid, kind, tier, company, site, text):
        if eid not in known:
            known.add(eid)
            fresh.append({"id": eid, "kind": kind, "tier": tier, "company": company, "site": site, "text": text[:700], "detectedAt": stamp})

    scanned = set()
    for comp in cfg["companies"]:
        own = re.compile(comp["own"])
        rows, ok = [], True
        for term in comp["terms"]:
            try:
                rows += fetch(term, key, get=get, sleep=sleep)
                ok_terms += 1
            except ApiError as e:
                errors.append(f"{term}({e})")
                ok = False
            sleep(0.3)
        if ok:
            scanned.add(comp["company"])
        by_site = {}
        for x in rows:
            name = str(x.get("fact_manage_nm") or "").strip()
            if name and own.search(name):
                by_site.setdefault(name, []).append(x)
        for name, xs in by_site.items():
            sid = f"{comp['company']}:{norm(name)}"
            seen_sites.add(sid)
            s = sites.get(sid)
            if s is None:
                s = {"id": sid, "company": comp["company"], "name": name, "area": xs[0].get("area_nm"), "firstSeen": stamp, "stacks": {}}
                sites[sid] = s
                if not first:
                    emit(f"stk:newsite:{sid}", "새 사업장(굴뚝 측정)", "A", comp["company"], name,
                         f"{name}({xs[0].get('area_nm') or '지역 미상'}) 굴뚝 자동측정 목록에 새로 나타남 — 배출구 {len(xs)}개. 새 공장·설비 가동 또는 이름 변경일 수 있음(회사 확인)")
            s.update(name=name, area=xs[0].get("area_nm") or s.get("area"), lastSeen=stamp)
            stacks = s.setdefault("stacks", {})
            present = set()
            for x in xs:
                code = str(x.get("stack_code") or "").strip()
                if not code:
                    continue
                present.add(code)
                st = stacks.get(code)
                if st is None:
                    st = {"firstSeen": stamp, "obs": []}
                    stacks[code] = st
                    if not first and not s.get("firstSeen") == stamp:
                        emit(f"stk:newstack:{sid}:{code}", "새 배출구", "A", comp["company"], name,
                             f"{name} 굴뚝 자동측정에 새 배출구 {code}번이 생김(측정 {x.get('mesure_dt')}, 가장 큰 측정값 {peak(x)}) — 새 설비 가동 가능성, 어떤 설비인지는 회사 확인")
                mdt = x.get("mesure_dt")
                if st.get("lastDt") == mdt and st.get("obs"):
                    st["missing"] = 0
                    continue  # 측정 시각이 그대로면 같은 관측을 두 번 쌓지 않는다
                st["obs"] = (st.get("obs") or [])[-(OBS_KEEP - 1):] + [[mdt, peak(x)]]
                st["lastDt"], st["missing"] = mdt, 0
            for code, st in stacks.items():
                if code not in present:
                    st["missing"] = st.get("missing", 0) + 1
                    if st["missing"] == MISSING_RUNS and not first:
                        emit(f"stk:gone:{sid}:{code}:{day}", "배출구 목록에서 빠짐", "B", comp["company"], name,
                             f"{name} 배출구 {code}번이 굴뚝 자동측정 목록에서 {MISSING_RUNS}번 연속 빠짐 — 설비 폐쇄·측정 대상 변경일 수 있음(회사 확인)")

            # 사업장 가동 판단: 평소 움직이던 배출구 가운데 멈춘 것
            judged = {code: stack_state(st, now) for code, st in stacks.items() if code in present}
            meaningful = {c: b for c, (state, b) in judged.items() if state in ("running", "stopped")}
            stopped = sorted((c for c, (state, _) in judged.items() if state == "stopped"), key=lambda c: -(judged[c][1] or 0))
            was = set(s.get("stopped") or [])
            newly = [c for c in stopped if c not in was]
            s["stopped"], s["meaningful"] = stopped, len(meaningful)
            top = sorted(meaningful, key=lambda c: -(meaningful[c] or 0))[:3]
            share = len(stopped) / len(meaningful) if meaningful else 0
            if newly:
                def desc(c):
                    st = stacks[c]
                    return f"{c}번(평소 {judged[c][1]:.1f}→최근 {st['obs'][-1][1] if st.get('obs') else '?'}, 측정 {st.get('lastDt')})"
                if len(stopped) >= 2 and share >= 0.5:
                    emit(f"stk:down:{sid}:{day}", "사업장 가동 중단 신호", "A", comp["company"], name,
                         f"{name}: 평소 움직이던 배출구 {len(meaningful)}개 중 {len(stopped)}개가 {STOP_RUNS}번 연속 평소의 10% 아래 — "
                         + ", ".join(desc(c) for c in stopped[:6]) + " · 설비 정지·정비·측정기 점검일 수 있음(회사 확인)")
                elif len(newly) >= 2 or any(c in top for c in newly):
                    emit(f"stk:stop:{sid}:{day}", "배출구 멈춤 신호", "B", comp["company"], name,
                         f"{name}: 배출구 {len(newly)}개가 {STOP_RUNS}번 연속 평소의 10% 아래(사업장 전체 평소 움직이던 {len(meaningful)}개 중 멈춤 {len(stopped)}개) — "
                         + ", ".join(desc(c) for c in newly[:6]) + " · 정비·점검일 수 있음(회사 확인)")
            if was and len(was) >= 2 and len(stopped) <= len(was) / 2 and s.get("downFlag"):
                emit(f"stk:up:{sid}:{day}", "사업장 재가동 신호", "B", comp["company"], name,
                     f"{name}: 멈췄던 배출구 {len(was)}개 중 {len(was) - len(stopped)}개 측정값이 평소 수준으로 돌아옴")
            s["downFlag"] = bool(len(stopped) >= 2 and share >= 0.5)

    # 목록에서 사라진 사업장(그 회사 검색을 다 읽었을 때만): 배출구 누락 횟수로 센다
    for sid, s in sites.items():
        if sid not in seen_sites and s["company"] in scanned:
            s["missingRuns"] = s.get("missingRuns", 0) + 1
            if s["missingRuns"] == MISSING_RUNS and not first:
                emit(f"stk:sitegone:{sid}", "사업장 목록에서 빠짐(굴뚝 측정)", "B", s["company"], s["name"],
                     f"{s['name']}이 굴뚝 자동측정 목록에서 {MISSING_RUNS}번 연속 빠짐 — 폐쇄·이름 변경·측정 대상 제외 확인")
        elif sid in seen_sites:
            s["missingRuns"] = 0

    total_terms = sum(len(c["terms"]) for c in cfg["companies"])
    status = "failed" if ok_terms == 0 else ("partial" if errors else "complete")
    checks = [{"source": "굴뚝 자동측정(CleanSYS)", "status": "ok" if not errors else ("failed" if not ok_terms else "partial"),
               "returned": len(seen_sites), "terms": f"{ok_terms}/{total_terms}", **({"error": "; ".join(errors[:5])} if errors else {})}]
    return {"schema": SCHEMA, "generatedAt": stamp, "status": status, "checks": checks,
            "baselineSince": prev.get("baselineSince") or stamp,
            "sites": sorted(sites.values(), key=lambda s: (s["company"], s["name"])), "events": (fresh + events)[:300],
            "rules": ["굴뚝 자동측정(TMS) 실시간 값을 이 감시가 3시간마다 쌓은 이력이다. 배출구 이름·설비 종류는 자료에 없다(번호만).",
                      "측정값이 평소의 10% 아래로 떨어진 것은 설비 정지·정비·측정기 점검·연료 전환일 수 있다. 가동 중단은 회사 확인 전 미확인.",
                      "평소 값이 1 미만인 배출구(원래 거의 0)는 멈춤 판단을 하지 않는다. 관측이 6번 모이기 전에는 판단하지 않는다.",
                      "조회 실패는 0이 아니라 미확인."],
            "confirmedScoops": 0}


def main():
    argparse.ArgumentParser(description="출입처 공장 굴뚝 측정(가동 신호) 감시(기자 전용 저장소로)").parse_args()
    import private_store
    now = dt.datetime.now(KST)
    key = (os.environ.get("DATA_GO_KR_KEY") or "").strip()
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    if not key:
        print("::warning title=kr-stacks::공공데이터 키(DATA_GO_KR_KEY) 미설정 — 미확인")
        return
    previous = None
    if token:
        try:
            previous = private_store.get("kr-stacks", token)
        except private_store.StoreError as e:
            print(f"::warning title=kr-stacks-state::이전 상태 조회 실패({e}) — 이번 실행은 기준선")
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    doc = run(cfg, now=now, previous=previous, key=key)
    new = [e for e in doc["events"] if e["detectedAt"] == doc["generatedAt"]]
    stacks = sum(len(s.get("stacks") or {}) for s in doc["sites"])
    stopped = sum(len(s.get("stopped") or []) for s in doc["sites"])
    print(f"::notice title=kr-stacks::상태 {doc['status']} · 사업장 {len(doc['sites'])} · 배출구 {stacks} · 지금 멈춤 판단 {stopped} · "
          f"이번 이벤트 {{'A': {sum(1 for e in new if e['tier'] == 'A')}, 'B': {sum(1 for e in new if e['tier'] == 'B')}}}")
    print(f"::notice title=kr-stacks-checks::{doc['checks'][0]}")
    if not token:
        print("::warning title=kr-stacks-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if doc["status"] == "failed":
        sys.exit("굴뚝 측정 조회 전체 실패 — 이전 결과 유지(0 아님)")
    status = private_store.put("kr-stacks", doc, token)
    print(f"::notice title=kr-stacks-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
