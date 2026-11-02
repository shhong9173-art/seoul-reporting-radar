"""출입처 상표 출원 감시(주 1회, KIPRIS Plus 상표 출원 속보 getAdvancedSearch) → 기자 전용 저장소.

- 출원인 이름(특허 수집과 같은 법인명)으로 최근 출원일 90일을 조회한다. 회사당 1회(500건 넘으면 2쪽까지).
- 모든 요청은 KIPRIS 공용 장부(kipris_account_ledger, 상표 몫 월 150회)를 거친다. 응답 22면 상표 쪽만 72시간 쉰다.
- 처음 보는 출원번호만 '새 출원'이다. 첫 실행은 기준선(새 출원 없음). 같은 날 같은 이름을 여러 상품류로 낸 것은 한 건으로 묶는다.
- 상표 출원은 출원 사실일 뿐이다. 제품 출시·사업 진출·차명 확정이 아니다. 조회 실패·대기는 0건이 아니라 미확인.
- 공개 로그는 건수만. 인증키·요청 주소·이미지 주소(fileToss)는 저장하지 않는다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kipris_account_ledger import KiprisAccountLedger, KiprisBudgetStop  # noqa: E402
from patent_hunt import ProviderResponseError, normalize, parse_response, request_xml  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
CONFIG = Path(__file__).resolve().parents[1] / "data" / "trademark_watch.json"
BASE = "https://plus.kipris.or.kr/kipo-api/kipi/trademarkInfoSearchService/getAdvancedSearch"
SCHEMA = "trademarks/v1"
SOURCE = "KIPRIS Plus 상표 출원 속보(getAdvancedSearch)"
# 권리구분·상표유형·표장구성 플래그는 그룹마다 1개 이상 true가 필수(명세서). 전부 true로 넓게 받는다.
FLAGS = ("application", "registration", "refused", "expiration", "withdrawal", "publication", "cancel", "abandonment",
         "trademark", "serviceMark", "trademarkServiceMark", "businessEmblem", "collectiveMark", "geoOrgMark",
         "internationalMark", "certMark", "geoCertMark",
         "character", "figure", "compositionCharacter", "figureComposition", "sound", "fragrance", "color",
         "dimension", "colorMixed", "hologram", "motion", "visual", "invisible")
APP_NO = re.compile(r"\d{13}\Z")
DATE8 = re.compile(r"20\d{6}\Z")


def now_kst():
    return dt.datetime.now(KST)


def ymd(v):
    v = re.sub(r"\D", "", str(v or ""))
    return f"{v[:4]}-{v[4:6]}-{v[6:8]}" if DATE8.fullmatch(v) else ""


def norm_title(title):
    return re.sub(r"[\W_]+", "", str(title or "").casefold())


def classes_of(raw):
    out = []
    for c in re.split(r"[|,\s]+", str(raw or "")):
        if c.isdigit() and 1 <= int(c) <= 45:
            out.append(f"{int(c):02d}")
    return out


def name_variants(names):
    """Legal-name forms as KIPRIS prints them: '현대자동차주식회사', '(주)현대자동차', '주식회사 X'."""
    out = set()
    for n in names:
        out.add(n)
        core = re.sub(r"\s*주식회사\s*", "", n).strip()
        if core:
            out.update({f"(주){core}", f"{core}(주)", f"주식회사{core}", f"{core}주식회사"})
    return tuple(sorted(out))


def owner_matches(raw, variants):
    """Each '|'-separated applicant compared as a whole legal name (customer numbers stripped)."""
    wanted = {normalize(v) for v in variants}
    parts = [re.sub(r"\d{6,}", "", p) for p in re.split(r"[|;]", str(raw or ""))]
    return any(normalize(p) in wanted for p in parts if p.strip())


def search(company_cfg, start, end, fetch, *, key, rows, max_pages):
    """All rows of one applicant in the window (or truncated=True). Raises on provider/transport errors."""
    query = company_cfg["names"][0]
    params = {"applicantName": query, "applicationDate": f"{start}~{end}", "numOfRows": str(rows)}
    params.update({f: "true" for f in FLAGS})
    got, total, requests = [], None, 0
    for page in range(1, max_pages + 1):
        requests += 1
        reply = parse_response(fetch(BASE + "?" + urlencode({**params, "pageNo": str(page), "ServiceKey": key})))
        if total is None:
            total = reply["total"]
        elif reply["total"] != total:
            raise ValueError("쪽마다 전체 건수가 다름 — 완전 조회 확인 불가")
        got.extend(reply["items"])
        if len(got) >= total or not reply["items"]:
            break
    return {"rows": got, "total": total or 0, "requests": requests, "complete": len(got) >= (total or 0)}


def group_filings(company_cfg, rows, *, variants, seen, titles_before, stamp, baseline, core):
    """Rows of one applicant → filings grouped by (title, application date)."""
    groups, unmatched, bad = {}, 0, 0
    for r in rows:
        number = re.sub(r"\D", "", str(r.get("applicationNumber") or ""))
        date = re.sub(r"\D", "", str(r.get("applicationDate") or ""))
        if not APP_NO.fullmatch(number) or not DATE8.fullmatch(date):
            bad += 1
            continue
        if not owner_matches(r.get("applicantName"), variants):
            unmatched += 1
            continue
        title = str(r.get("title") or "").strip()[:120]
        key = (norm_title(title) or f"#{number}", date)
        g = groups.setdefault(key, {"title": title, "applicationDate": ymd(date), "numbers": [], "classes": set(),
                                    "statuses": set(), "agent": str(r.get("agentName") or "")[:60],
                                    "coApplicants": str(r.get("applicantName") or "")[:200]})
        g["numbers"].append(number)
        g["classes"].update(classes_of(r.get("classificationCode")))
        if r.get("applicationStatus"):
            g["statuses"].add(str(r["applicationStatus"])[:10])
    filings = []
    company = company_cfg["company"]
    for (nt, date), g in groups.items():
        numbers = sorted(set(g["numbers"]))
        new_numbers = [n for n in numbers if n not in seen]
        is_new = bool(new_numbers) and not baseline
        title_new = bool(g["title"]) and not nt.startswith("#") and nt not in titles_before
        classes = sorted(g["classes"])
        core_hit = sorted(set(classes) & set(core))
        tier = None
        if is_new:
            tier = "B" if (title_new and core_hit and not company_cfg.get("related")) else "C"
        filings.append({
            "id": f"tm:{company}:{nt}:{date}",
            "company": company,
            "related": bool(company_cfg.get("related")),
            "title": g["title"] or "(문자 없는 도형 상표)",
            "applicationDate": g["applicationDate"],
            "applicationNumbers": numbers,
            "newNumbers": new_numbers if not baseline else [],
            "classes": classes,
            "coreClasses": core_hit,
            "statuses": sorted(g["statuses"]),
            "agent": g["agent"],
            "applicants": g["coApplicants"],
            "isNew": is_new,
            "titleNew": title_new and not baseline,
            "tier": tier,
            "firstSeen": stamp,
        })
    return filings, unmatched, bad


RETRY_DAYS = 6  # 월요일 정기 실행 뒤 이 안의 평일(화~금)에는 실패·대기한 회사만 다시 묻는다


def retry_targets(cfg, previous, now, *, env=None):
    """None이면 전체 실행(월요일·강제·직전 결과 없음·오래됨). 집합이면 그 회사만 다시 묻는다(빈 집합이면 건너뜀).
    11-02: 영풍이 '응답 출원인 이름 불일치'로 실패한 채 다음 월요일까지 미확인으로 남았다 — KIPRIS 한도를 아끼며 실패한 곳만 평일에 다시."""
    env = os.environ if env is None else env
    if str(env.get("FORCE_RUN", "")).lower() in ("1", "true", "yes") or now.astimezone(KST).weekday() == 0:
        return None
    if not isinstance(previous, dict) or previous.get("schema") != SCHEMA or not previous.get("baselineSince"):
        return None
    try:
        age = (now - dt.datetime.fromisoformat(str(previous.get("generatedAt")))).total_seconds() / 86400
    except (TypeError, ValueError):
        return None
    if not 0 <= age < RETRY_DAYS:
        return None
    by_src = {c.get("source"): c for c in previous.get("checks") or [] if isinstance(c, dict)}
    out = set()
    for c in cfg["applicants"]:
        pc = by_src.get(f"상표 {c['company']}")
        if pc is None or pc.get("status") in ("failed", "waiting"):
            out.add(c["company"])
    return out


def run(cfg, *, now, previous=None, key="", ledger=None, fetch=None, only=None):
    stamp = now.isoformat(timespec="seconds")
    prev = previous if isinstance(previous, dict) and previous.get("schema") == SCHEMA else None
    # A stored document without a baseline (every earlier run failed or waited) is still a baseline run.
    baseline = not (prev or {}).get("baselineSince")
    seen = dict((prev or {}).get("seen") or {})
    titles = {c: dict(v) for c, v in ((prev or {}).get("titles") or {}).items() if isinstance(v, dict)}
    old_filings = {f["id"]: f for f in (prev or {}).get("filings", []) if isinstance(f, dict) and f.get("id")}
    prev_checks = {x.get("source"): x for x in (prev or {}).get("checks", []) if isinstance(x, dict)}
    end = now.astimezone(KST).date()
    start = end - dt.timedelta(days=int(cfg.get("windowDays", 90)))
    s8, e8 = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    checks, fresh = [], []
    cap = int(cfg.get("runCallCap", 34))
    used = 0
    for c in cfg["applicants"]:
        src = f"상표 {c['company']}"
        if only is not None and c["company"] not in only and src in prev_checks:
            checks.append(prev_checks[src])  # 평일 재시도: 정상이던 회사는 월요일 결과 그대로
            continue
        if not key:
            checks.append({"source": src, "status": "unset", "error": "KIPRIS_SERVICE_KEY 없음"})
            continue
        if ledger is not None and not ledger.should_probe("trademark"):
            until = (ledger.public().get("effectiveNextProbeAt") or {}).get("trademark")
            checks.append({"source": src, "status": "waiting", "reason": "provider_22_cooldown", "until": until})
            continue
        room = min(cap - used, ledger.remaining("trademark") if ledger is not None else cap - used)
        if room <= 0:
            checks.append({"source": src, "status": "waiting",
                           "reason": "run_cap" if used >= cap else "monthly_trademark_limit"})
            continue
        try:
            res = search(c, s8, e8, fetch, key=key, rows=int(cfg.get("rowsPerPage", 500)),
                         max_pages=min(int(cfg.get("maxPagesPerApplicant", 2)), room))
        except KiprisBudgetStop as stop:
            checks.append({"source": src, "status": "waiting", "reason": stop.reason})
            continue
        except ProviderResponseError as e:
            used += 1
            code = str(e).rsplit(" ", 1)[-1]
            checks.append({"source": src, "status": "failed", "error": f"제공기관 코드 {code}(뜻 미공개)",
                           "providerCode": code, "category": e.category})
            continue
        except Exception as e:  # transport / parse; never the URL or body
            used += 1
            checks.append({"source": src, "status": "failed", "error": type(e).__name__})
            continue
        used += res["requests"]
        # 회사마다 첫 읽기는 기준선: 새로 더한 회사, 조회 이름을 바꾼 회사, 예전 결과에 이름 미확인으로 남은 회사
        # (11-02: 석유화학·정유 6곳 등 10곳이 '이름 미확인·0건' — 띄어 쓴 법인명으로 바꾼 첫 실행에 90일 치 출원이 신규로 뜨면 안 된다)
        query = c["names"][0]
        pc = prev_checks.get(src)
        first_read = baseline or pc is None or (pc.get("query") != query if "query" in pc else pc.get("nameVerified") is False)
        variants = name_variants(c["names"])
        core = cfg["industries"][c["industry"]]["core"]
        before = set(titles.get(c["company"], {}))
        filings, unmatched, bad = group_filings(c, res["rows"], variants=variants, seen=seen, titles_before=before,
                                                stamp=stamp, baseline=first_read, core=core)
        for f in filings:
            for n in f["applicationNumbers"]:
                seen.setdefault(n, end.isoformat())
            nt = norm_title(f["title"]) if not f["title"].startswith("(") else ""
            if nt:
                titles.setdefault(c["company"], {}).setdefault(nt, end.isoformat())
            old = old_filings.get(f["id"])
            if old:  # keep the first sighting; add numbers seen later (more classes)
                f["firstSeen"] = old.get("firstSeen", f["firstSeen"])
                if not f["isNew"]:
                    f["isNew"], f["tier"], f["titleNew"] = old.get("isNew", False), old.get("tier"), old.get("titleNew", False)
                    f["newNumbers"] = old.get("newNumbers", [])
                else:
                    f["newNumbers"] = sorted(set(old.get("newNumbers", [])) | set(f["newNumbers"]))
                    f["addedClassesAt"] = stamp
            old_filings[f["id"]] = f
            if f["isNew"] and (not old or f.get("addedClassesAt") == stamp):
                fresh.append(f["id"])
        chk = {"source": src, "status": "ok" if res["complete"] else "partial", "rawTotal": res["total"],
               "kept": sum(len(f["applicationNumbers"]) for f in filings), "filings": len(filings),
               "requests": res["requests"], "query": query, **({"baseline": True} if first_read and not baseline else {})}
        if not res["complete"]:
            chk["error"] = f"{res['total']}건 중 {len(res['rows'])}건만 읽음(쪽 한도)"
        if unmatched:
            chk["otherApplicants"] = unmatched
            if not filings and res["rows"]:
                # KIPRIS 출원인 검색은 이름 일부만 같아도 돌려준다(11-02 probe 95f: '주식회사영풍' → '영풍제약 주식회사',
                # '주식회사 영풍' → '주식회사 영풍큐비클'). 이 회사 출원이 있었다면 같은 검색에 함께 나온다 — 실패가 아니라 0건이다.
                others = sorted({re.sub(r"\(?\d{6,}\)?", "", p).strip()[:40] for r in res["rows"]
                                 for p in re.split(r"[|;]", str(r.get("applicantName") or ""))
                                 if p.strip() and not owner_matches(p, variants)})[:3]
                chk["note"] = f"응답 {unmatched}건은 이름 일부만 같은 다른 출원인({', '.join(others)}) — 이 회사 출원 없음"
        if bad:
            chk["badRows"] = bad
        if c.get("nameVerified") is False:
            chk["nameVerified"] = False
            if res["total"] == 0:
                chk["note"] = "출원인 이름 미확인 — 0건이 이름 불일치 때문일 수 있음"
        if only is not None:
            chk["retriedAt"] = stamp
        checks.append(chk)
    keep_from = (end - dt.timedelta(days=int(cfg.get("keepFilingDays", 120)))).isoformat()
    filings = [f for f in old_filings.values() if str(f.get("firstSeen", ""))[:10] >= keep_from
               or str(f.get("applicationDate", "")) >= keep_from]
    filings.sort(key=lambda f: (f.get("firstSeen", ""), f.get("applicationDate", "")), reverse=True)
    seen_from = (end - dt.timedelta(days=int(cfg.get("keepSeenDays", 400)))).isoformat()
    seen = {k: v for k, v in seen.items() if v >= seen_from}
    titles = {c: dict(list(v.items())[-3000:]) for c, v in titles.items()}
    bad = [c for c in checks if c["status"] not in ("ok", "unset", "waiting")]
    waiting = [c for c in checks if c["status"] == "waiting"]
    any_ok = any(c["status"] in ("ok", "partial") for c in checks)
    doc = {
        "schema": SCHEMA, "generatedAt": stamp, "source": SOURCE,
        "status": ("unset" if all(c["status"] == "unset" for c in checks) else
                   "complete" if not bad and not waiting and any_ok else
                   "waiting" if waiting and not any_ok and not bad else "partial"),
        "window": ((prev or {}).get("window") if only is not None and (prev or {}).get("window") else
                   {"from": start.isoformat(), "to": end.isoformat(), "field": "출원일"}),
        **({"retry": {"at": stamp, "companies": sorted(only)}} if only is not None else {}),
        "baselineSince": (prev or {}).get("baselineSince") or (stamp if any_ok else None),
        "checks": checks, "filings": filings[:1500], "fresh": fresh,
        "seen": seen, "titles": titles,
        "kipris": ledger.public() if ledger is not None else None,
        "rules": [
            "상표 출원은 출원 사실이다. 제품 출시·사업 진출·차명 확정이 아니다(방어 출원·예비 출원이 흔함).",
            "'새 출원'은 이 감시가 처음 본 출원번호다. KIPRIS 공개가 출원일보다 늦게 올라오므로 출원일이 몇 주 전일 수 있다.",
            "'처음 보는 이름'은 감시 시작 이후 그 회사 출원에서 처음 본 이름이다. 그 전에 같은 이름을 냈을 수 있다 — KIPRIS에서 상표명으로 다시 조회한다.",
            "같은 날 같은 이름을 여러 상품류로 낸 것은 한 건으로 묶는다(출원번호는 상품류마다 다름).",
            "조회 실패·대기(호출 한도·응답 22)는 0건이 아니라 미확인.",
        ],
        "confirmedScoops": 0,
    }
    return doc


def main():
    argparse.ArgumentParser(description="출입처 상표 출원 감시(기자 전용 저장소로)").parse_args()
    now = now_kst()
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    key = os.environ.get("KIPRIS_SERVICE_KEY", "").strip()
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    import private_store
    previous = None
    if token:
        try:
            previous = private_store.get("trademarks", token)
        except private_store.StoreError as e:
            print(f"::warning title=trademarks-state::이전 상태 조회 실패({e}) — 저장하지 않고 끝냄(기준선 재설정 방지)")
            sys.exit(1)
    if private_store.late_scheduled_duplicate(previous, now) or private_store.recent_duplicate(previous, now):
        return
    only = retry_targets(cfg, previous, now)
    if only is not None and not only:
        print("::notice title=trademarks::이번 주 정기 조회가 모두 정상 — 평일 재시도할 회사 없음(KIPRIS 호출 0)")
        return
    if only is not None:
        print(f"::notice title=trademarks-retry::평일 재시도 — 실패·대기한 회사만: {', '.join(sorted(only))}")
    ledger = KiprisAccountLedger(now=now) if key else None
    try:
        doc = run(cfg, now=now, previous=previous, key=key, ledger=ledger, only=only,
                  fetch=ledger.fetcher("trademark", request_xml) if ledger else None)
    finally:
        if ledger is not None:
            ledger.persist()
    counts = {}
    for c in doc["checks"]:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    new_n = len(doc["fresh"])
    b_n = sum(1 for f in doc["filings"] if f["id"] in set(doc["fresh"]) and f.get("tier") == "B")
    used = (doc.get("kipris") or {}).get("byPurpose", {}).get("trademark")
    print(f"::notice title=trademarks::상태 {doc['status']} · 회사 {' · '.join(f'{k} {v}' for k, v in sorted(counts.items()))}"
          f" · 새 출원 묶음 {new_n}(B {b_n}) · 이번 달 상표 호출 {used if used is not None else '-'}")
    errors = sorted({c.get("error") for c in doc["checks"] if c.get("error") and c["status"] == "failed"})
    if errors:
        print(f"::notice title=trademarks-errors::{', '.join(errors)[:300]}")
    if not token:
        print("::warning title=trademarks-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    # Earlier filings, seen numbers and names are carried forward, so storing a failed/waiting run loses
    # nothing and lets radar_today show "대기·실패" instead of silence.
    status = private_store.put("trademarks", doc, token)
    print(f"::notice title=trademarks-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)
    if any(c["status"] == "failed" for c in doc["checks"]):
        sys.exit("일부 회사 조회 실패 — 해당 회사는 미확인(0건 아님)")


if __name__ == "__main__":
    main()
