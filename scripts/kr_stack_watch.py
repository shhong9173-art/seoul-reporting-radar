"""출입처 공장 굴뚝 측정(가동 신호) 감시 — 한국환경공단 굴뚝 자동측정기기(TMS, CleanSYS) 실시간 측정결과, 기자 전용 저장소 'kr-stacks'.

- 출입처 사업장(data/stack_watch.json 이름 규칙)의 배출구별 최신 측정값(먼지·SOx·NOx 등 중 가장 큰 값)을 실행마다(3시간 간격)
  쌓는다. API는 지금 값만 주므로 이력은 이 감시가 쌓은 것이다.
- 배출구 멈춤 신호: 평소 값(직전 관측 중앙값)이 1 이상이던 배출구가 연달아 STOP_RUNS번 평소의 10% 아래(또는 0.3 아래)로 떨어지면
  '멈춤'. 사업장에서 평소 움직이던 배출구 절반 이상(2개 이상)이 멈추면 A(사업장 가동 중단 신호), 두 곳 이상이거나 큰 배출구면 B.
- 새 배출구 번호·새 사업장: 실시간 값만 오는 자료라 쉬던 설비가 다시 측정되기 시작해도 '새 번호'로 보인다. 그 사업장을 14일 넘게
  지켜본 뒤 처음 보인 번호만 A(새 설비 또는 오래 쉬던 설비 재가동), 7~14일 B, 그 전은 C(간헐 가동·자료 지연일 수 있음).
  (10-31 운영: 영풍 석포 5·6번이 감시 하루 만에 A로 떴다.) 목록에서 빠진 배출구(두 번 연속) B. 멈췄던 사업장이 다시 움직이면 B.
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
MATURE_RUNS = 6        # 새 배출구·새 사업장을 '새것'으로 볼 만큼 그 사업장(감시)을 지켜본 실행 수
NEW_A_DAYS = 14        # 새 배출구·새 사업장 A: 그 사업장(새 사업장은 감시)을 이만큼 지켜본 뒤 처음 보인 것
NEW_B_DAYS = 7         # 이만큼~NEW_A_DAYS면 B, 그 전은 C
BURST = 3              # 한 실행에 이만큼 이상 새로 보이면 새 설비가 아니라 목록 보강으로 본다(10-30 고려아연 온산 24개)
STOP_RUNS = 3          # 연달아 이만큼 낮으면 멈춤(3시간 간격이면 9시간)
MEANINGFUL = 1.0       # 평소 값이 이보다 작으면 멈춤 판단을 하지 않는다(원래 거의 0인 배출구)
LOW_ABS = 0.3
LOW_REL = 0.10
MISSING_RUNS = 2
KEEP_EVENTS_DAYS = 60


# 공공데이터포털 게이트웨이 코드 중 일시 오류: 04 HTTP_ERROR, 05 SERVICE_TIMEOUT_ERROR. 키·권한·한도(20·22·30 등)는 다시 부르지 않는다.
TRANSIENT_GATEWAY = {"04", "05"}

class ApiError(RuntimeError):
    pass


def age_days(since, now):
    try:
        return (now - dt.datetime.fromisoformat(str(since))).total_seconds() / 86400
    except (TypeError, ValueError):
        return 0.0


def new_tier(days):
    return "A" if days >= NEW_A_DAYS else "B" if days >= NEW_B_DAYS else "C"


def retier_new(events, sites, baseline_since):
    """저장된 '새 배출구'·'새 사업장' 이벤트를 지켜본 기간 규칙으로 다시 매긴다(예전 규칙으로 하루 만에 A가 된 것 바로잡기)."""
    for e in events:
        kind, at = e.get("kind"), e.get("detectedAt")
        if kind == "새 배출구":
            sid = ":".join(str(e.get("id", "")).split(":")[2:-1])
            since = (sites.get(sid) or {}).get("firstSeen") or baseline_since
        elif kind == "새 사업장(굴뚝 측정)":
            since = baseline_since
        else:
            continue
        try:
            days = age_days(since, dt.datetime.fromisoformat(str(at)))
        except (TypeError, ValueError):
            continue
        tier = new_tier(days)
        if tier != e.get("tier") and {"A": 0, "B": 1, "C": 2}.get(tier, 2) > {"A": 0, "B": 1, "C": 2}.get(e.get("tier"), 2):
            e["tier"] = tier
            e["text"] = (e.get("text") or "") + f" — 이 사업장을 {days:.1f}일만 지켜본 때라 간헐 가동·측정 자료 지연일 수 있어 {tier}로 바로잡음"


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
        if code and code.group(1) in TRANSIENT_GATEWAY:  # 게이트웨이 시간 초과·연결 오류: 한 번 더
            err = f"코드 {code.group(1)}"
            continue
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


POL_KO = {"tsp": "먼지", "sox": "황산화물", "nox": "질소산화물", "hcl": "염화수소", "hf": "불화수소", "nh3": "암모니아", "co": "일산화탄소"}
EXCEED_KEEP = 20


def fnum(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def exceedances(x):
    """측정값이 그 배출구의 배출허용기준(같은 줄의 *_exhst_perm_stdr_value)을 넘은 오염물질: [(물질, 측정값, 기준)]."""
    out = []
    for p in POLLUTANTS:
        m, s = fnum(x.get(f"{p}_mesure_value")), fnum(x.get(f"{p}_exhst_perm_stdr_value"))
        if m is not None and s is not None and s > 0 and m > s:
            out.append((p, m, s))
    return out


def collapse_bursts(events):
    """저장된 '새 배출구' 이벤트 가운데 같은 사업장·같은 실행에 BURST개 이상이면 C '배출구 목록 보강' 한 줄로 바꾼다
    (10-30 13:36: 고려아연 온산제련소 배출구 24개가 한꺼번에 A로 뜸 — 첫 실행 기준선 때 일부 배출구 값이 아직 없었던 것)."""
    groups = {}
    for e in events:
        if e.get("kind") == "새 배출구":
            groups.setdefault((e.get("company"), e.get("site"), e.get("detectedAt")), []).append(e)
    drop, add = set(), []
    for (company, site, at), es in groups.items():
        if len(es) < BURST:
            continue
        drop |= {e["id"] for e in es}
        codes = sorted((re.search(r"새 배출구 (\S+)번", e.get("text") or "") or [None, "?"])[1] for e in es)
        add.append({"id": f"stk:burst:{company}:{site}:{at}", "kind": "배출구 목록 보강", "tier": "C", "company": company, "site": site, "detectedAt": at,
                    "text": f"{site} 굴뚝 자동측정 목록에 배출구 {len(es)}개가 한꺼번에 새로 보임({', '.join(codes[:12])}{' 외' if len(codes) > 12 else ''}) — "
                            "측정 자료가 늦게 들어온 것일 수 있어 새 설비로 보지 않음(처음엔 A로 띄웠다가 바로잡음)"})
    return [e for e in events if e["id"] not in drop] + add


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
    events = collapse_bursts([e for e in prev.get("events") or [] if isinstance(e, dict) and e.get("detectedAt", "") >= keep_from])
    retier_new(events, sites, prev.get("baselineSince"))
    known = {e["id"] for e in events}
    fresh, errors, ok_terms, seen_sites = [], [], 0, set()
    day = now.date().isoformat()

    def settle(prefix, note):
        """목록에서 빠졌다던 것이 다시 나타나면 그 이벤트를 C로 내리고 '다시 나타남'을 붙인다(일시적 누락)."""
        for e in fresh + events:
            if str(e.get("id", "")).startswith(prefix) and e.get("tier") != "C":
                e["tier"], e["text"] = "C", (e.get("text") or "") + note

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
                watched = age_days(prev.get("baselineSince"), now) if prev.get("baselineSince") else 0.0
                if not first:
                    # 감시를 14일 넘게 돌린 뒤 처음 나타난 사업장만 A(초기에는 검색 결과가 덜 차거나 쉬던 사업장일 수 있다)
                    tier = new_tier(watched)
                    emit(f"stk:newsite:{sid}", "새 사업장(굴뚝 측정)", tier, comp["company"], name,
                         f"{name}({xs[0].get('area_nm') or '지역 미상'}) 굴뚝 자동측정 목록에 새로 나타남 — 배출구 {len(xs)}개. 새 공장·설비 가동 또는 이름 변경일 수 있음(회사 확인)"
                         + ("" if tier == "A" else f" · 감시 {watched:.1f}일째라 쉬던 사업장이 다시 측정된 것일 수 있음"))
            s.update(name=name, area=xs[0].get("area_nm") or s.get("area"), lastSeen=stamp)
            stacks = s.setdefault("stacks", {})
            # 이 사업장을 본 실행 수(예전 저장본에는 없으니 배출구 관측 수 가운데 가장 큰 값으로 시작)
            s["runs"] = s.get("runs", max([len(v.get("obs") or []) for v in stacks.values()] or [0])) + 1
            present, new_codes = set(), []
            for x in xs:
                code = str(x.get("stack_code") or "").strip()
                if not code:
                    continue
                present.add(code)
                st = stacks.get(code)
                if st is not None and st.get("missing", 0) >= MISSING_RUNS:
                    settle(f"stk:gone:{sid}:{code}:", f" — 이후 다시 나타남(측정 {x.get('mesure_dt')}, 일시적 누락)")
                if st is None:
                    st = {"firstSeen": stamp, "obs": []}
                    stacks[code] = st
                    if not first and not s.get("firstSeen") == stamp:
                        new_codes.append((code, x))
                mdt = x.get("mesure_dt")
                if st.get("lastDt") == mdt and st.get("obs"):
                    st["missing"] = 0
                    continue  # 측정 시각이 그대로면 같은 관측을 두 번 쌓지 않는다
                st["obs"] = (st.get("obs") or [])[-(OBS_KEEP - 1):] + [[mdt, peak(x)]]
                st["lastDt"], st["missing"] = mdt, 0
                # 배출허용기준 초과: 새 측정 시각마다 한 번. 처음 넘으면 B, 다음 측정(이 감시의 다음 실행)에도 넘으면 A(지속)
                over = {p: (m, lim) for p, m, lim in exceedances(x)}
                runs = st.setdefault("exceed", {})
                for p in list(runs):
                    if p not in over:
                        del runs[p]
                for p, (m, lim) in over.items():
                    ep = runs.get(p) or {"start": mdt, "count": 0, "first": [m, lim]}
                    ep["count"] += 1
                    runs[p] = ep
                    s.setdefault("exceedLog", [])
                    s["exceedLog"] = (s["exceedLog"] + [{"stack": code, "pollutant": p, "value": m, "limit": lim, "at": mdt}])[-EXCEED_KEEP:]
                    odd = " — 기준의 20배 넘는 값이라 측정기 이상값일 수 있음" if m > lim * 20 else ""
                    what = f"{name} 배출구 {code}번 {POL_KO[p]} 측정값 {m:g}이 배출허용기준 {lim:g}을 넘음(기준의 {m / lim:.1f}배, 측정 {mdt}){odd}"
                    tail = " · 실시간 자동측정 값(확정 전). 측정기 점검·교정 중 값일 수 있음 — 초과 판정·행정처분은 한국환경공단·관할 지자체 확인"
                    if first:
                        continue
                    if ep["count"] == 1:
                        emit(f"stk:exceed:{sid}:{code}:{p}:{ep['start']}", "배출허용기준 초과(측정값)", "B", comp["company"], name, what + tail)
                    elif ep["count"] == 2:
                        emit(f"stk:exceed2:{sid}:{code}:{p}:{ep['start']}", "배출허용기준 초과 지속", "A", comp["company"], name,
                             f"{what} — {ep['start']} 측정부터 이 감시의 실행 2번 연속 초과(처음 {ep['first'][0]:g})" + tail)
            if new_codes:
                days = age_days(s.get("firstSeen"), now)
                tier = new_tier(days)
                if s["runs"] > MATURE_RUNS and len(new_codes) < BURST and tier != "C":
                    for code, x in new_codes:
                        emit(f"stk:newstack:{sid}:{code}", "새 배출구", tier, comp["company"], name,
                             f"{name} 굴뚝 자동측정에 새 배출구 {code}번이 생김(측정 {x.get('mesure_dt')}, 가장 큰 측정값 {peak(x)}, "
                             f"이 사업장을 {days:.0f}일·{s['runs'] - 1}번 지켜보는 동안 없던 번호) — "
                             + ("새 설비 가동 또는 오래 쉬던 설비 재가동 가능성" if tier == "A" else "간헐 가동 설비가 다시 측정된 것일 수 있음(새 설비 여부 미확인)")
                             + ", 어떤 설비인지는 회사 확인")
                else:
                    codes = [c for c, _ in new_codes]
                    emit(f"stk:burst:{comp['company']}:{name}:{stamp}", "배출구 목록 보강", "C", comp["company"], name,
                         f"{name} 굴뚝 자동측정 목록에 배출구 {len(codes)}개가 새로 보임({', '.join(codes[:12])}{' 외' if len(codes) > 12 else ''}) — "
                         + ("한꺼번에 여러 개라 " if len(codes) >= BURST else f"이 사업장을 {days:.1f}일·{s['runs'] - 1}번만 봐서 ")
                         + "간헐 가동·측정 자료 지연일 수 있어 새 설비로 보지 않음")
            for code, st in stacks.items():
                if code not in present:
                    st["missing"] = st.get("missing", 0) + 1
                    # 6번 넘게 관측된 배출구만(초기에는 측정 자료가 늦게 들어와 목록이 들쑥날쑥하다)
                    if st["missing"] == MISSING_RUNS and not first and len(st.get("obs") or []) >= MIN_OBS:
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
            if s.get("runs", 0) < MATURE_RUNS:  # 예전 규칙으로 B가 된 이른 사업장의 '빠짐'도 C로(10-30 엘에스엠앤엠)
                settle(f"stk:sitegone:{sid}", f" — 이 사업장을 {s.get('runs', 0) or '몇'}번만 봐서 일시적 누락일 수 있음")
            if s["missingRuns"] == MISSING_RUNS and not first:
                mature = s.get("runs", 0) >= MATURE_RUNS
                emit(f"stk:sitegone:{sid}", "사업장 목록에서 빠짐(굴뚝 측정)", "B" if mature else "C", s["company"], s["name"],
                     f"{s['name']}이 굴뚝 자동측정 목록에서 {MISSING_RUNS}번 연속 빠짐 — "
                     + ("폐쇄·이름 변경·측정 대상 제외 확인" if mature else f"이 사업장을 {s.get('runs', 0)}번만 봐서 일시적 누락일 수 있음"))
        elif sid in seen_sites:
            if s.get("missingRuns", 0) >= MISSING_RUNS:
                settle(f"stk:sitegone:{sid}", f" — 이후 다시 나타남({stamp[:16]}, 일시적 누락)")
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
                      f"새 배출구 번호·새 사업장은 쉬던 설비가 다시 측정돼도 생긴다. 그 사업장을 {NEW_A_DAYS}일 넘게 지켜본 뒤 처음 보인 것만 A, {NEW_B_DAYS}~{NEW_A_DAYS}일 B, 그 전은 C.",
                      "배출허용기준 초과는 같은 줄에 실린 그 배출구의 물질별 기준과 실시간 측정값을 비교한 것이다. 처음 넘으면 B, 다음 실행에도 넘으면 A. 측정기 점검·교정 값일 수 있고 초과 판정·처분은 환경공단·지자체 확인.",
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
