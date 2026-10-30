"""출입처 사업장 인력 감시(국민연금 가입 사업장, 공공데이터 3046071 V2) — 기자 전용 저장소 'kr-workforce'.

- 자사 사업장: data/workforce_watch.json의 이름 규칙에 맞는 출입처 사업장(본사·공장)의 월별 국민연금 가입자 수, 그달 신규 취득·상실.
  지난달 대비 크게 줄면 A, 크게 늘거나 눈에 띄게 변하면 B. 사업장 탈퇴·새 자사 사업장도 이벤트.
- 공사·용역 현장: 시공사가 '시공사/일용/현대제철 당진 ○○ 신설공사'처럼 출입처 이름을 넣어 만든 현장 사업장. 새 이름이 생기면
  신설·증설·신축 같은 투자 낱말(보수·정비 제외)은 A, 그 밖 공사는 출입처별로 묶어 B.
- 자료는 월 단위(자료생성년월). 매 실행은 표지 조회 한 번으로 새 달이 나왔는지 보고, 새 달일 때만 전체를 읽는다. 남는 시간에는
  자사 사업장의 지난 12개월 가입자 수를 조금씩 채운다.
- 첫 실행은 기준선(이벤트 없음). 키 값은 출력하지 않는다. 조회 실패는 0명·0건이 아니라 미확인.
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
SCHEMA = "kr_workforce/v1"
CONFIG = ROOT / "data" / "workforce_watch.json"
API = "https://apis.data.go.kr/B552015/NpsBplcInfoInqireServiceV2/"
ROWS = 100
MAX_PAGES = 8
HISTORY_MONTHS = 13
BUDGET_S = 22 * 60
PROJECT_DETAIL_MAX = 120
KEEP_EVENTS_DAYS = 120
KEEP_PROJECTS = 600
SEEN_MAX = 8000
SIDO = {"11": "서울", "26": "부산", "27": "대구", "28": "인천", "29": "광주", "30": "대전", "31": "울산", "36": "세종", "41": "경기",
        "42": "강원", "51": "강원", "43": "충북", "44": "충남", "45": "전북", "52": "전북", "46": "전남", "12": "전남광주", "47": "경북",
        "48": "경남", "50": "제주"}
# 시공사·용역사가 출입처 이름을 넣어 만든 현장 사업장의 모양
PROJECT_SHAPE = re.compile(r"/|-\s*\((?:일용|상용)\)|\((?:일용|상용)\)|현장|공사|PJT|프로젝트", re.I)
HOUSING = re.compile(r"아파트|더샵|주택|재개발|재건축|오피스텔|힐스테이트|자이|푸르지오|래미안|어린이집|학교")
INVEST = re.compile(r"신설|증설|신축|신공장|신규\s*(?:공장|라인|설비)|공장\s*건설|건설공사|구축|프로젝트|PJT|라인", re.I)
MAINT = re.compile(r"보수|개선|교체|정비|유지|철거|해체|청소|도장|단가|보강|이설|수리|점검|관리|용역|방수|조경|석면|폐기물|경비|미화|급식")
CONSTRUCTION = re.compile(r"공사|설치|PJT|프로젝트|건설|구축|현장", re.I)


class ApiError(RuntimeError):
    pass


class Api:
    """국민연금 사업장 V2. 실패는 한 번만 다시 시도하고, 키 오류(코드 30 등)는 다시 시도하지 않는다. 키 값은 오류에 넣지 않는다."""

    def __init__(self, key, *, get=None, sleep=time.sleep):
        self.key, self.sleep, self.calls = key, sleep, 0
        if get is None:
            import requests
            get = requests.get
        self.get = get

    def call(self, op, params, *, rows=ROWS, page=1):
        err = None
        for attempt in (0, 1):
            if attempt:
                self.sleep(3.0)
            self.calls += 1
            try:
                r = self.get(API + op, params={"serviceKey": self.key, "pageNo": page, "numOfRows": rows, "dataType": "json", **params}, timeout=60)
            except Exception as e:  # noqa: BLE001 — network failure is recorded by class name only
                err = type(e).__name__
                continue
            text = r.text or ""
            code = re.search(r'"returnReasonCode"\s*:\s*"?(\d+)', text)
            if code:  # 게이트웨이 오류(키 미등록·한도 초과 등): 다시 불러도 같다
                raise ApiError(f"코드 {code.group(1)}")
            if r.status_code != 200:
                err = f"HTTP {r.status_code}"
                continue
            try:
                d = json.loads(text)
            except ValueError:
                err = "비JSON 응답"
                continue
            res = d.get("response") or {}
            rc = str((res.get("header") or {}).get("resultCode") or "")
            if rc and rc != "00":
                raise ApiError(f"결과 코드 {rc}")
            body = res.get("body") or {}
            items = body.get("items")
            items = items.get("item") if isinstance(items, dict) else items
            items = items if isinstance(items, list) else ([items] if items else [])
            self.sleep(0.3)
            return body.get("totalCount"), items
        raise ApiError(err or "응답 없음")


def norm(name):
    return re.sub(r"\s+", "", str(name or "").replace("（", "(").replace("）", ")"))


def region_of(x):
    return f"{x.get('ldongAddrMgplDgCd') or ''}{x.get('ldongAddrMgplSgguCd') or ''}"


def region_label(region, addr=None):
    if addr:
        return " ".join(str(addr).split()[:3])
    return f"{SIDO.get(region[:2], '시도 ' + region[:2])} 시군구코드 {region[2:]}" if region else "지역 미상"


def month_before(ym, n=1):
    y, m = int(ym[:4]), int(ym[4:6]) - n
    while m <= 0:
        y, m = y - 1, m + 12
    return f"{y}{m:02d}"


def ym_label(ym):
    return f"{ym[:4]}-{ym[4:6]}" if ym else "?"


def num(v):
    try:
        return int(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def project_tier(name):
    """공사·용역 현장 이름의 등급: 투자 낱말(보수·정비 없이) A, 그 밖 공사 B, 용역·관리 C."""
    if INVEST.search(name) and not MAINT.search(name):
        return "A"
    if CONSTRUCTION.search(name) and not MAINT.search(name):
        return "B"
    return "C"


def delta_event(site, month):
    """지난달 대비 가입자 수 변화: 줄어든 폭이 max(30명, 3%) 이상이면 A, 늘어난 폭이 같은 기준 이상이면 B,
    max(15명, 1.5%) 이상 변동이면 B. 그 밖은 None."""
    h = site.get("history") or {}
    cur, prev = (h.get(month) or {}).get("members"), (h.get(month_before(month)) or {}).get("members")
    if cur is None or prev is None or prev <= 0:
        return None
    d = cur - prev
    pct = d / prev * 100
    big, mid = max(30, prev * 0.03), max(15, prev * 0.015)
    if d <= -big:
        tier, kind = "A", "인력 감소"
    elif d >= big:
        tier, kind = "B", "인력 증가"
    elif abs(d) >= mid:
        tier, kind = "B", "인력 변동"
    else:
        return None
    m = h.get(month) or {}
    flow = f" · 그달 신규 취득 {m['acq']}·상실 {m['loss']}" if m.get("acq") is not None and m.get("loss") is not None else ""
    text = (f"{site['name']}({region_label(site.get('region', ''), site.get('addr'))}) 국민연금 가입자 {prev:,}→{cur:,}명"
            f"({d:+,}명, {pct:+.1f}%){flow} — {ym_label(month)} 자료")
    return tier, kind, text


def _event(events, stamp, eid, kind, tier, company, month, text, **extra):
    events.append({"id": eid, "kind": kind, "tier": tier, "company": company, "month": month, "text": text[:700], "detectedAt": stamp, **extra})


def run(cfg, *, now, previous=None, api, clock=time.monotonic, budget=BUDGET_S):
    t0 = clock()
    left = lambda: budget - (clock() - t0)  # noqa: E731
    stamp = now.isoformat(timespec="seconds")
    prev = previous if isinstance(previous, dict) else {}
    first = not prev.get("month")
    sites = {s["id"]: s for s in prev.get("sites") or [] if isinstance(s, dict) and s.get("id")}
    seen_projects = set(prev.get("projectSeen") or [])
    projects = {p["id"]: p for p in prev.get("projects") or [] if isinstance(p, dict) and p.get("id")}
    keep_from = (now - dt.timedelta(days=KEEP_EVENTS_DAYS)).isoformat()
    events = [e for e in prev.get("events") or [] if isinstance(e, dict) and e.get("detectedAt", "") >= keep_from]
    known_events = {e["id"] for e in events}
    fresh_events = []
    errors, checks = [], []
    month = prev.get("month")
    scan_status = prev.get("scanStatus")

    def emit(eid, *a, **k):
        if eid not in known_events:
            known_events.add(eid)
            _event(fresh_events, stamp, eid, *a, **k)

    # 1) 표지 조회: 새 달이 나왔나
    try:
        _, it = api.call("getBassInfoSearchV2", {"wkplNm": cfg["sentinel"]}, rows=1)
        latest = it[0].get("dataCrtYm") if it else None
    except ApiError as e:
        latest = None
        errors.append(f"표지 조회 {e}")
    if not latest:
        return _doc(prev, stamp, "failed", [{"source": "국민연금 사업장", "status": "failed", "returned": 0, "error": "; ".join(errors) or "표지 조회 0건"}],
                    month, scan_status, sites, projects, seen_projects, events, api)

    scanned_companies = set()
    if latest != month or scan_status != "complete":
        # 2) 새 달 전체 읽기: 출입처별 검색어로 최신 달 줄만(최신 달이 먼저 나오고, 앞 달 줄이 섞이면 멈춘다)
        prior_month, month = month, latest
        seen_now, failed_terms, by_company_new = set(), [], {}
        for comp in cfg["companies"]:
            own_rx, word_rx = re.compile(comp["own"]), re.compile(comp["word"])
            ok = True
            for term in comp["terms"]:
                for page in range(1, MAX_PAGES + 1):
                    try:
                        _, items = api.call("getBassInfoSearchV2", {"wkplNm": term}, page=page)
                    except ApiError as e:
                        failed_terms.append(f"{term}({e})")
                        ok = False
                        break
                    cur = [x for x in items if x.get("dataCrtYm") == latest]
                    for x in cur:
                        name = str(x.get("wkplNm") or "").strip()
                        region = region_of(x)
                        if own_rx.search(name):
                            sid = f"{comp['company']}:{norm(name)}:{region}"
                            seen_now.add(sid)
                            s = sites.get(sid)
                            is_new = s is None
                            s = s or {"id": sid, "company": comp["company"], "name": name, "region": region, "firstSeen": stamp, "history": {}, "seqs": {}}
                            sites[sid] = s
                            was = s.get("status")
                            s.update(name=name, status=str(x.get("wkplJnngStcd") or ""), bzno=x.get("bzowrRgstNo"), lastMonth=latest,
                                     addr=(x.get("wkplRoadNmDtlAddr") or "").strip() or s.get("addr"))
                            s["seqs"][latest] = x.get("seq")
                            s["_new"], s["_was"] = is_new, was
                        elif PROJECT_SHAPE.search(name) and word_rx.search(name) and not HOUSING.search(name):
                            pid = f"{norm(name)}:{region}"
                            if pid in seen_projects:
                                continue
                            seen_projects.add(pid)
                            tier = project_tier(name)
                            rec = {"id": pid, "company": comp["company"], "name": name, "region": region, "addr": (x.get("wkplRoadNmDtlAddr") or "").strip() or None,
                                   "seq": x.get("seq"), "month": latest, "tier": tier, "firstSeen": stamp, "baseline": first}
                            if tier != "C":
                                projects[pid] = rec
                                if not first:
                                    by_company_new.setdefault(comp["company"], []).append(rec)
                    if len(cur) < len(items) or len(items) < ROWS:
                        break
                else:
                    failed_terms.append(f"{term}({MAX_PAGES}쪽까지만)")
                    ok = False
            if ok:
                scanned_companies.add(comp["company"])

        # 자사 사업장: 최신 달 가입자 수와 그달 취득·상실
        site_fail = 0
        for sid in sorted(seen_now):
            s = sites[sid]
            if latest in s["history"]:
                continue
            if left() < 90:
                errors.append("시간 한도 — 자사 사업장 일부는 다음 실행에서")
                break
            try:
                _, d = api.call("getDetailInfoSearchV2", {"seq": s["seqs"][latest]}, rows=1)
                _, p = api.call("getPdAcctoSttusInfoSearchV2", {"seq": s["seqs"][latest]}, rows=1)
            except ApiError:
                site_fail += 1
                continue
            d0, p0 = (d[0] if d else {}), (p[0] if p else {})
            s["history"][latest] = {"members": num(d0.get("jnngpCnt")), "acq": num(p0.get("nwAcqzrCnt")), "loss": num(p0.get("lssJnngpCnt"))}
            s.update(industry=d0.get("vldtVlKrnNm") or s.get("industry"), adptDt=d0.get("adptDt") or s.get("adptDt"), scsnDt=d0.get("scsnDt"))
        if site_fail:
            errors.append(f"자사 사업장 상세 {site_fail}곳 실패")

        if not first:
            for sid in sorted(seen_now):
                s = sites[sid]
                if s.get("_new"):
                    adpt = str(s.get("adptDt") or "")
                    if adpt and adpt[:6] >= month_before(latest, 6):
                        emit(f"wf:new:{sid}", "새 자사 사업장", "A", s["company"], latest,
                             f"{s['name']}({region_label(s['region'], s.get('addr'))}) 국민연금 사업장 새로 적용 {adpt[:4]}-{adpt[4:6]}-{adpt[6:8]}"
                             f" · 가입자 {((s['history'].get(latest) or {}).get('members'))}명 · 업종 {s.get('industry') or '미상'} — {ym_label(latest)} 자료")
                elif s.get("_was") == "1" and s.get("status") == "2":
                    emit(f"wf:quit:{sid}:{latest}", "사업장 탈퇴", "A", s["company"], latest,
                         f"{s['name']}({region_label(s['region'], s.get('addr'))}) 국민연금 사업장 탈퇴로 바뀜(탈퇴일 {s.get('scsnDt') or '미상'}) — {ym_label(latest)} 자료")
            # 지난달 있던 자사 사업장이 이번 달 목록에 없음(그 회사 검색을 다 읽었을 때만)
            for sid, s in sites.items():
                if s.get("lastMonth") == prior_month and sid not in seen_now and s["company"] in scanned_companies and prior_month:
                    emit(f"wf:gone:{sid}:{latest}", "자사 사업장 목록에서 빠짐", "B", s["company"], latest,
                         f"{s['name']}({region_label(s['region'], s.get('addr'))}) — {ym_label(prior_month)}에 있던 사업장이 {ym_label(latest)} 검색 결과에 없음(이름 변경·통합·탈퇴 확인)")

            # 새 공사·용역 현장: 상세(적용일·가입자·업종)를 붙여 A는 하나씩, B는 출입처별로 묶어서
            reads = 0
            for company, recs in by_company_new.items():
                recs.sort(key=lambda r: r["tier"])
                for r in recs:
                    if reads >= PROJECT_DETAIL_MAX or left() < 60:
                        break
                    reads += 1
                    try:
                        _, d = api.call("getDetailInfoSearchV2", {"seq": r["seq"]}, rows=1)
                    except ApiError:
                        continue
                    d0 = d[0] if d else {}
                    r.update(adptDt=d0.get("adptDt"), members=num(d0.get("jnngpCnt")), industry=d0.get("vldtVlKrnNm"))
                for r in [r for r in recs if r["tier"] == "A"]:
                    emit(f"wf:proj:{r['id']}", "새 공사 현장", "A", company, latest, _project_line(r))
                bs = [r for r in recs if r["tier"] == "B"]
                if bs:
                    emit(f"wf:projs:{company}:{latest}:{len(bs)}", "새 공사 현장 묶음", "B", company, latest,
                         f"{company} 이름이 든 새 공사·용역 현장 {len(bs)}곳({ym_label(latest)} 자료): "
                         + " / ".join(_project_line(r, short=True) for r in bs[:6]) + (f" 외 {len(bs) - 6}곳" if len(bs) > 6 else ""))
        for s in sites.values():
            s.pop("_new", None)
            s.pop("_was", None)
        checks.append({"source": "국민연금 사업장(출입처 검색)", "status": "ok" if not failed_terms else ("partial" if scanned_companies else "failed"),
                       "returned": len(seen_now), **({"error": "; ".join(failed_terms[:5])} if failed_terms else {})})
        scan_status = "complete" if not failed_terms and not any("시간 한도" in e for e in errors) else "partial"
    else:
        checks.append({"source": "국민연금 사업장(출입처 검색)", "status": "ok", "returned": 0, "note": f"새 달 없음({ym_label(latest)} 그대로)"})

    # 3) 남는 시간: 자사 사업장 지난 12개월 채우기(이름으로 다시 찾아 달별 seq → 상세). 처음 채워진 지난달 비교도 이벤트로(첫 수집 표시)
    filled = 0
    for s in sorted(sites.values(), key=lambda s: (s.get("backfilledMonth") == month, len(s.get("history") or {}))):
        if s.get("backfilledMonth") == month or left() < 75:
            continue
        try:
            _, items = api.call("getBassInfoSearchV2", {"wkplNm": s["name"]})
        except ApiError as e:
            errors.append(f"지난 달 채우기 {e}")
            break
        for x in items:
            if norm(x.get("wkplNm")) == norm(s["name"]) and region_of(x) == s["region"] and x.get("dataCrtYm"):
                s.setdefault("seqs", {})[x["dataCrtYm"]] = x.get("seq")
        recent = sorted(s["seqs"], reverse=True)[:2]
        want = [ym for ym in sorted(s["seqs"], reverse=True)[:HISTORY_MONTHS] if ym not in s["history"]]
        done = True
        for ym in want:
            if left() < 45:
                done = False
                break
            try:
                _, d = api.call("getDetailInfoSearchV2", {"seq": s["seqs"][ym]}, rows=1)
                # 그달 취득·상실은 최근 두 달만(오래된 달은 가입자 수만 — 호출 수를 줄인다)
                _, p = api.call("getPdAcctoSttusInfoSearchV2", {"seq": s["seqs"][ym]}, rows=1) if ym in recent else (None, [])
            except ApiError:
                done = False
                continue
            d0, p0 = (d[0] if d else {}), (p[0] if p else {})
            s["history"][ym] = {"members": num(d0.get("jnngpCnt")), "acq": num(p0.get("nwAcqzrCnt")), "loss": num(p0.get("lssJnngpCnt"))}
            filled += 1
        s["seqs"] = {k: v for k, v in sorted(s["seqs"].items(), reverse=True)[:HISTORY_MONTHS + 2]}
        s["history"] = {k: v for k, v in sorted(s["history"].items(), reverse=True)[:HISTORY_MONTHS + 2]}
        if done:
            s["backfilledMonth"] = month
    # 4) 지난달 대비 변화: 최신 달과 그 앞 달 수치가 다 있는 사업장을 한 번씩(첫 실행은 기준선이라 다음 실행에서)
    if not first and month:
        for s in sites.values():
            h = s.get("history") or {}
            if s.get("evaluated") == month or month not in h or month_before(month) not in h:
                continue
            s["evaluated"] = month
            ev = delta_event(s, month)
            if ev:
                tier, kind, text = ev
                emit(f"wf:delta:{s['id']}:{month}", kind, tier, s["company"], month, text, siteId=s["id"])
    checks.append({"source": "국민연금 사업장(지난 12개월 채우기)", "status": "ok", "returned": filled,
                   "pending": sum(1 for s in sites.values() if s.get("backfilledMonth") != month)})
    if errors:
        checks[0] = {**checks[0], "status": "partial" if checks[0]["status"] == "ok" else checks[0]["status"],
                     "error": "; ".join(([checks[0]["error"]] if checks[0].get("error") else []) + errors)[:400]}
    events = fresh_events + events
    status = "failed" if checks[0]["status"] == "failed" else ("partial" if any(c["status"] != "ok" for c in checks) else "complete")
    return _doc(prev, stamp, status, checks, month, scan_status, sites, projects, seen_projects, events, api)


def _project_line(r, short=False):
    adpt = str(r.get("adptDt") or "")
    when = f"적용 {adpt[:4]}-{adpt[4:6]}-{adpt[6:8]}" if len(adpt) == 8 else "적용일 미확인"
    members = r["members"] if r.get("members") is not None else "?"
    if short:
        return f"「{r['name']}」({when}, 가입자 {members}명)"
    return (f"「{r['name']}」 · {region_label(r.get('region', ''), r.get('addr'))} · {when} · 가입자 {members}명 · 업종 {r.get('industry') or '미상'}"
            f" — {ym_label(r.get('month'))} 자료, 현장 이름만 확인(사업 규모·발주 내용은 회사 확인)")


def _doc(prev, stamp, status, checks, month, scan_status, sites, projects, seen_projects, events, api):
    keep = sorted(projects.values(), key=lambda p: (p.get("month") or "", p.get("firstSeen") or ""), reverse=True)[:KEEP_PROJECTS]
    return {"schema": SCHEMA, "generatedAt": stamp, "status": status, "checks": checks, "month": month, "scanStatus": scan_status,
            "baselineSince": prev.get("baselineSince") or stamp, "apiCalls": api.calls,
            "sites": sorted(sites.values(), key=lambda s: (s["company"], s["name"])), "projects": keep,
            "projectSeen": sorted(seen_projects)[-SEEN_MAX:], "events": events[:400],
            "rules": ["국민연금 가입자 수는 사업장 전체 직원 수가 아니다(만 60세 이상·일부 외국인·단시간 근로자 등 빠질 수 있음). 본사 일괄 신고 사업장은 공장별 숫자가 아니다.",
                      "월 자료(자료생성년월)다. 지난달 대비 증감 이유(희망퇴직·전환배치·분할·신규 채용)는 회사 확인 전 미확인.",
                      "공사·용역 현장 이름은 시공사가 국민연금 사업장으로 붙인 이름이다. 사업 규모·발주 금액·착공 여부는 회사·지자체 확인이 필요하다.",
                      "조회 실패·시간 한도로 못 읽은 사업장은 0명이 아니라 미확인."],
            "confirmedScoops": 0}


def main():
    argparse.ArgumentParser(description="출입처 사업장 인력 감시(국민연금, 기자 전용 저장소로)").parse_args()
    import private_store
    now = dt.datetime.now(KST)
    key = (os.environ.get("DATA_GO_KR_KEY") or "").strip()
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    if not key:
        print("::warning title=kr-workforce::공공데이터 키(DATA_GO_KR_KEY) 미설정 — 미확인")
        return
    previous = None
    if token:
        try:
            previous = private_store.get("kr-workforce", token)
        except private_store.StoreError as e:
            print(f"::warning title=kr-workforce-state::이전 상태 조회 실패({e}) — 이번 실행은 기준선")
    if private_store.late_scheduled_duplicate(previous, now):
        return
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    doc = run(cfg, now=now, previous=previous, api=Api(key))
    new = [e for e in doc["events"] if e["detectedAt"] == doc["generatedAt"]]
    tiers = {t: sum(1 for e in new if e["tier"] == t) for t in "AB"}
    checks = " ;; ".join(f"{c['source']}={c['status']}({c.get('returned', 0)}{', ' + c['error'] if c.get('error') else ''}{', ' + c['note'] if c.get('note') else ''})" for c in doc["checks"])
    filled = sum(1 for s in doc["sites"] if len(s.get("history") or {}) >= 2)
    print(f"::notice title=kr-workforce::상태 {doc['status']} · 자료 {doc['month']} · 자사 사업장 {len(doc['sites'])}(2개월 이상 {filled}) · "
          f"공사 현장 보관 {len(doc['projects'])} · 이번 이벤트 {tiers} · API {doc['apiCalls']}회")
    print(f"::notice title=kr-workforce-checks::{checks}")
    if not token:
        print("::warning title=kr-workforce-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if doc["status"] == "failed":
        sys.exit("국민연금 사업장 조회 실패 — 이전 결과 유지(0명 아님)")
    status = private_store.put("kr-workforce", doc, token)
    print(f"::notice title=kr-workforce-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
