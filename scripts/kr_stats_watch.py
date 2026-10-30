"""국내 월간 통계 감시: 한국은행 ECOS 품목별 물가지수, KOSIS(철강협회 철강 생산·광공업동향 품목), KAIDA 수입 승용차 브랜드별 신규등록,
현대차·기아 IR 모델별·해외 공장별 월간 판매 엑셀(carsales.py).

- 같은 계열(같은 품목·같은 지수 기준·같은 단위) 안에서만 비교한다. 지수 기준(2020=100, 2022.12=100)이 다른 품목끼리 비교하지 않는다.
- 새 달 수치가 처음 보이면 그 달 기준으로 신호를 만든다: '그 달(값) 이후 최고/최저 — N개월 만'(12개월 이상), 전년 같은 달 대비 큰 변동,
  전년 대비 N개월 연속 증가·감소, KAIDA 출입처 브랜드 순위 변화. '역대'는 판정하지 않는다(조회 범위만).
- 결과는 기자 전용 저장소(kr-stats)로만. 공개 로그는 건수만. 조회 실패·미설정은 0건이 아니다.
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
SCHEMA = "kr_stats/v1"
CONFIG = ROOT / "data" / "kr_stats.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
ECOS_API = "https://ecos.bok.or.kr/api/StatisticSearch"
KOSIS_API = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
CENSUS_API = "https://api.census.gov/data/timeseries/intltrade/imports/hs"
KOREA = "5800"  # Census country code: KOREA, SOUTH (probe 2026-10-28)
KAIDA_PAGE = "https://www.kaida.co.kr/ko/statistics/NewRegistList.do"
KAIDA_API = "https://www.kaida.co.kr/ko/statistics/NewRegistListAjax.do"
KEEP_POINTS = 60
EVENT_KEEP_DAYS = 400


def now_kst():
    return dt.datetime.now(KST)


class Http:
    def __init__(self, session=None, sleep=time.sleep, gap=0.5):
        if session is None:
            import requests
            session = requests.Session()
        self.s, self.sleep, self.gap = session, sleep, gap

    def call(self, method, url, *, timeout=40, ok=(200,), **kw):
        kw.setdefault("headers", UA)
        for attempt in (1, 2):
            try:
                r = self.s.request(method, url, timeout=timeout if attempt == 1 else 70, **kw)
            except Exception as e:  # noqa: BLE001 — 미확인
                self.sleep(self.gap)
                if attempt == 1 and type(e).__name__ in ("ReadTimeout", "ConnectTimeout", "ConnectionError"):
                    self.sleep(5.0)
                    continue
                return None, type(e).__name__
            self.sleep(self.gap)
            if r.status_code not in ok:
                return None, f"HTTP {r.status_code}"
            return r, None
        return None, "error"


def ym(s):
    s = re.sub(r"[^\d]", "", str(s or ""))
    return f"{s[:4]}-{s[4:6]}" if len(s) >= 6 else None


def prev_ym(p, n=1):
    y, m = int(p[:4]), int(p[5:7]) - n
    while m <= 0:
        y, m = y - 1, m + 12
    return f"{y:04d}-{m:02d}"


def months_between(a, b):
    return (int(b[:4]) - int(a[:4])) * 12 + int(b[5:7]) - int(a[5:7])


def num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


# ---------- sources ----------

def ecos_series(s, key, since, now, http):
    start, end = since.replace("-", ""), now.strftime("%Y%m")
    r, err = http.call("GET", f"{ECOS_API}/{key}/json/kr/1/2000/{s['stat']}/M/{start}/{end}/{s['item']}")
    if err:
        raise RuntimeError(err)
    body = r.json()
    if "StatisticSearch" not in body:
        res = body.get("RESULT") or {}
        raise RuntimeError(f"{res.get('CODE', '응답 형식')} {res.get('MESSAGE', '')}".strip()[:120])
    rows = body["StatisticSearch"].get("row") or []
    if s.get("variant"):
        rows = [x for x in rows if x.get("ITEM_CODE2") == s["variant"]]
    pts = [{"p": ym(x.get("TIME")), "v": num(x.get("DATA_VALUE"))} for x in rows]
    unit = (rows[-1].get("UNIT_NAME") if rows else "") or ""
    name = (rows[-1].get("ITEM_NAME1") if rows else "") or ""
    return [p for p in pts if p["p"] and p["v"] is not None], unit, name


def kosis_series(s, key, since, now, http):
    r, err = http.call("GET", KOSIS_API, params={"method": "getList", "apiKey": key, "itmId": s["itm"], "objL1": s["obj"], "format": "json",
                                                 "jsonVD": "Y", "prdSe": "M", "startPrdDe": since.replace("-", ""), "endPrdDe": now.strftime("%Y%m"),
                                                 "orgId": s["org"], "tblId": s["tbl"]}, timeout=60)
    if err:
        raise RuntimeError(err)
    body = r.json()
    if isinstance(body, dict):
        raise RuntimeError(f"{body.get('err', '')} {body.get('errMsg', '응답 형식')}".strip()[:120])
    rows = [x for x in body if str(x.get("ITM_ID")) == s["itm"]]
    pts = [{"p": ym(x.get("PRD_DE")), "v": num(x.get("DT"))} for x in rows]
    unit = (rows[-1].get("UNIT_NM") if rows else "") or ""
    name = (f"{rows[-1].get('C1_NM')} {rows[-1].get('ITM_NM')}" if rows else "") or ""
    return [p for p in pts if p["p"] and p["v"] is not None], unit, name


def parse_kaida(text):
    """Brand rows of the 'brand monthly summary' table: name, this month, share, … ; Total row. None if the month is not published."""
    try:
        html = json.loads(text).get("statisticsPopup") or ""
    except ValueError:
        return None
    brands = {}
    for name, cells in re.findall(r"detailViewClick\('\d+'\);\">([^<]+)</a></td>(.*?)</tr>", html, re.S):
        vals = re.findall(r"<td[^>]*>([^<]*)</td>", cells)
        if vals:
            brands[name.strip()] = {"units": num(vals[0]) or 0, "share": num(vals[1]) if len(vals) > 1 else None}
    total = re.search(r">\s*Total\s*</td>\s*<td[^>]*>([^<]*)</td>", html)
    tot = num(total.group(1)) if total else sum(b["units"] for b in brands.values())
    if not brands or not tot:
        return None
    return {"total": tot, "brands": brands}


def kaida(cfg, now, previous, http):
    kc = cfg["kaida"]
    months = dict((previous or {}).get("kaidaMonths") or {})
    latest_try = prev_ym(f"{now.year:04d}-{now.month:02d}")
    want = [prev_ym(latest_try, i) for i in range(kc.get("months", 49))]
    if not months:
        todo = want  # first run: back-fill
    else:
        # the newest month (re-read until published), the month before (KAIDA revises), and any gap after the last stored month
        todo = list(dict.fromkeys([latest_try, prev_ym(latest_try), *[p for p in want if p > max(months)]]))
    http.call("GET", KAIDA_PAGE)
    hdr = {**UA, "X-Requested-With": "XMLHttpRequest", "Referer": KAIDA_PAGE}
    got, err, missing = 0, None, []
    for p in todo:
        r, e = http.call("POST", KAIDA_API, headers=hdr, data={"searchStart": p.replace("-", ""), "searchEnd": "", "programId": "117",
                                                              "layId": "NewBrandSummary", "regionId": "", "buytypeId": ""})
        if e:
            err = e
            if p == latest_try:
                continue
            break
        t = parse_kaida(r.text)
        if t is None:
            missing.append(p)
            continue
        months[p] = t
        got += 1
    keep = sorted(months)[-kc.get("months", 49):]
    months = {p: months[p] for p in keep}
    status = "failed" if err and not got and not months else ("partial" if err else "ok")
    check = {"source": "KAIDA 수입 승용차 신규등록", "status": status, "read": got, "months": len(months),
             "latest": max(months) if months else None, **({"error": err} if err else {}),
             **({"notPublished": missing[:3]} if missing else {})}
    return months, check


# ---------- signals ----------

def census_series(s, key, since, now, http):
    """US general imports from Korea, monthly value (GEN_VAL_MO, USD) → million USD. One call per HS code."""
    r, err = http.call("GET", CENSUS_API, params={"get": "GEN_VAL_MO,CTY_CODE,I_COMMODITY", "time": f"from {since}",
                                                  "CTY_CODE": KOREA, "COMM_LVL": s.get("level", "HS4"), "I_COMMODITY": s["hs"], "key": key}, timeout=60)
    if err:
        raise RuntimeError(err)
    text = (r.text or "").strip()
    if not text:
        raise RuntimeError("값 없음")
    try:
        rows = r.json()
    except ValueError:
        raise RuntimeError("JSON 아님(키 확인 필요)")
    if not isinstance(rows, list) or len(rows) < 2 or "time" not in rows[0] or "GEN_VAL_MO" not in rows[0]:
        raise RuntimeError("응답 형식")
    head = rows[0]
    it, iv, ic = head.index("time"), head.index("GEN_VAL_MO"), head.index("CTY_CODE")
    pts = []
    for x in rows[1:]:
        v = num(x[iv])
        if x[ic] == KOREA and v is not None:
            pts.append({"p": ym(x[it]), "v": round(v / 1e6, 2)})
    return [p for p in pts if p["p"]], "백만달러", f"US Census 수입 {s.get('level', 'HS4')} {s['hs']} · KOREA, SOUTH · GEN_VAL_MO"


def series_signals(pts, rules, yoy_pct):
    """pts oldest→newest. Statements about the newest month only, each with the dates and values it rests on."""
    if len(pts) < 2:
        return {}, []
    cur = pts[-1]
    by = {p["p"]: p["v"] for p in pts}
    prev = pts[-2]
    ly = by.get(prev_ym(cur["p"], 12))
    mom = round((cur["v"] - prev["v"]) / prev["v"] * 100, 2) if prev["v"] else None
    yoy = round((cur["v"] - ly) / ly * 100, 2) if ly else None
    out = []
    gap = rules.get("recordGapMonths", 12)
    for high in (True, False):
        word = "최고" if high else "최저"
        prior = next((p for p in reversed(pts[:-1]) if (p["v"] >= cur["v"] if high else p["v"] <= cur["v"])), None)
        if prior is None and months_between(pts[0]["p"], cur["p"]) >= gap:
            out.append({"kind": f"조회 범위 {word}", "text": f"{pts[0]['p']} 이후 {word}(조회 범위 안)"})
        elif prior is not None and months_between(prior["p"], cur["p"]) >= gap:
            n = months_between(prior["p"], cur["p"])
            same = prior["v"] == cur["v"]
            out.append({"kind": f"{word}(기간)", "text": f"{prior['p']}({prior['v']:,g}) 이후 {word} — {n}개월 만" + (" (그 달과 같은 값)" if same else "")})
    if yoy is not None and abs(yoy) >= yoy_pct:
        out.append({"kind": "전년 대비 큰 변동", "text": f"전년 같은 달({prev_ym(cur['p'], 12)}, {ly:,g}) 대비 {yoy:+.1f}%"})
    streak, sign = 0, None
    for p in reversed(pts):
        base = by.get(prev_ym(p["p"], 12))
        if not base:
            break
        s = 1 if p["v"] > base else -1 if p["v"] < base else 0
        if s == 0 or (sign is not None and s != sign):
            break
        sign, streak = s, streak + 1
    if streak >= rules.get("streakMonths", 6):
        out.append({"kind": "연속 증감", "text": f"전년 같은 달 대비 {streak}개월 연속 {'증가' if sign > 0 else '감소'}"})
    hi = max(pts, key=lambda p: p["v"])
    lo = min(pts, key=lambda p: p["v"])
    return {"period": cur["p"], "value": cur["v"], "prev": prev["v"], "mom": mom, "lastYear": ly, "yoy": yoy,
            "high": hi, "low": lo, "span": [pts[0]["p"], cur["p"]]}, out


def kaida_signals(months, cfg, rules):
    """Rank and record statements for beat brands in the newest month."""
    if not months:
        return [], []
    beats = cfg["kaida"]["beats"]
    order = sorted(months)
    cur_p = order[-1]
    cur = months[cur_p]
    rank = {b: i + 1 for i, (b, _) in enumerate(sorted(cur["brands"].items(), key=lambda kv: -kv[1]["units"]))}
    prev = months.get(prev_ym(cur_p))
    prank = {b: i + 1 for i, (b, _) in enumerate(sorted(prev["brands"].items(), key=lambda kv: -kv[1]["units"]))} if prev else {}
    rows, out = [], []
    for brand in [*beats, *cfg["kaida"].get("watch", [])]:
        if brand not in cur["brands"]:
            continue
        pts = [{"p": p, "v": months[p]["brands"].get(brand, {}).get("units")} for p in order]
        pts = [x for x in pts if x["v"] is not None]
        summary, sig = series_signals(pts, rules, 30) if len(pts) >= 2 else ({}, [])
        r = {"brand": brand, "beat": beats.get(brand), "units": cur["brands"][brand]["units"], "share": cur["brands"][brand]["share"],
             "rank": rank.get(brand), "prevRank": prank.get(brand), **{k: summary.get(k) for k in ("mom", "yoy", "lastYear", "high", "low", "span")}}
        rows.append(r)
        if brand not in beats:
            continue
        if r["prevRank"] and r["rank"] != r["prevRank"]:
            out.append({"brand": brand, "kind": "순위 변화", "text": f"{brand} 순위 {r['prevRank']}위 → {r['rank']}위({prev_ym(cur_p)} → {cur_p})",
                        "top": min(r["rank"], r["prevRank"]) <= 3})
        for s in sig:
            if s["kind"] in ("조회 범위 최고", "조회 범위 최저", "최고(기간)", "최저(기간)", "전년 대비 큰 변동"):
                out.append({"brand": brand, "kind": s["kind"], "text": f"{brand} 신규등록 {r['units']:,.0f}대 · {s['text']}", "top": s["kind"] != "전년 대비 큰 변동"})
        # a non-beat brand passing a beat brand this month
        for other, orank in rank.items():
            if other in beats or other not in prank or brand not in prank:
                continue
            if orank < rank[brand] and prank[other] > prank[brand]:
                out.append({"brand": brand, "kind": "순위 역전", "text": f"순위 역전: {other} {orank}위 · {brand} {rank[brand]}위({cur_p}) — 직전 달은 {brand} {prank[brand]}위 · {other} {prank[other]}위",
                            "top": rank[brand] <= 5})
    return sorted(rows, key=lambda r: r["rank"] or 99), out


# ---------- run ----------

def run(cfg, *, now, previous=None, http=None, ecos_key="", kosis_key="", census_key="", car_sales=True):
    http = http or Http()
    stamp = now.isoformat(timespec="seconds")
    rules = cfg.get("signals", {})
    since = cfg.get("since", "2016-01")
    prev_series = {s["id"]: s for s in (previous or {}).get("series", []) if isinstance(s, dict) and s.get("id")}
    keep_from = (now - dt.timedelta(days=EVENT_KEEP_DAYS)).isoformat()
    events = [e for e in (previous or {}).get("events", []) if isinstance(e, dict) and e.get("detectedAt", "") >= keep_from]
    have = {e.get("id") for e in events}
    baseline = previous is None
    series, checks = [], []
    for src, items, key, fetch in (("ECOS", cfg.get("ecos", []), ecos_key, ecos_series), ("KOSIS", cfg.get("kosis", []), kosis_key, kosis_series),
                                   ("CENSUS", cfg.get("census", []), census_key, census_series)):
        if not key:
            checks.append({"source": f"{src} 통계", "status": "unset", "error": f"{src}_API_KEY 미설정"})
            series += [{**prev_series[s["id"]], "stale": True} for s in items if s["id"] in prev_series]
            continue
        ok = fails = 0
        errs = []
        for s in items:
            try:
                pts, unit, name = fetch(s, key, since, now, http)
                if not pts:
                    raise RuntimeError("값 없음")
            except Exception as e:  # noqa: BLE001
                fails += 1
                errs.append(f"{s['label']}: {str(e)[:60]}")
                if s["id"] in prev_series:
                    series.append({**prev_series[s["id"]], "stale": True})
                continue
            ok += 1
            pts.sort(key=lambda p: p["p"])
            summary, sig = series_signals(pts, rules, s.get("yoyPct", 10))
            old = prev_series.get(s["id"])
            fresh = not old or (old.get("summary") or {}).get("period") != summary.get("period")
            row = {"id": s["id"], "source": src, "label": s["label"], "officialName": name, "unit": unit, "kind": s.get("kind") or ("trade" if src == "CENSUS" else None),
                   "beats": s.get("beats", []), "summary": summary, "signals": sig, "points": pts[-KEEP_POINTS:],
                   "updatedAt": stamp if fresh else (old or {}).get("updatedAt", stamp)}
            series.append(row)
            if fresh and not baseline and old is not None:
                for x in sig:
                    eid = f"st:{s['id']}:{summary['period']}:{x['kind']}"
                    if eid not in have:
                        events.append({"id": eid, "kind": "월간 통계", "signal": x["kind"], "series": s["id"], "period": summary["period"],
                                       "company": "·".join(s.get("beats", [])), "detectedAt": stamp,
                                       "text": f"{s['label']} {summary['period']} {summary['value']:,g}({unit}) · {x['text']}"})
                        have.add(eid)
        checks.append({"source": f"{src} 통계", "status": "ok" if not fails else ("failed" if not ok else "partial"), "ok": ok, "failed": fails,
                       **({"error": "; ".join(errs[:3])} if errs else {})})
    months, kcheck = kaida(cfg, now, previous, http)
    checks.append(kcheck)
    brands, ksig = kaida_signals(months, cfg, rules)
    latest = max(months) if months else None
    prev_latest = max((previous or {}).get("kaidaMonths") or {"": 0}) if previous else None
    if latest and not baseline and latest != prev_latest:
        for x in ksig:
            eid = f"kaida:{latest}:{x['brand']}:{x['kind']}"
            if eid not in have:
                events.append({"id": eid, "kind": "수입차 등록", "signal": x["kind"], "top": x.get("top", False), "period": latest,
                               "company": cfg["kaida"]["beats"].get(x["brand"], x["brand"]), "detectedAt": stamp, "text": f"KAIDA {latest} · {x['text']}"})
                have.add(eid)
    cars, car_events = (previous or {}).get("carSales") or {}, []
    if car_sales:
        import carsales
        try:
            cars, car_events, ccheck = carsales.collect(cars, now, http, baseline=baseline)
        except Exception as e:  # noqa: BLE001 — 판매 엑셀 실패가 다른 통계를 막지 않게(직전 블록 유지, 미확인)
            ccheck = {"source": "완성차 판매(현대차·기아 IR)", "status": "failed", "ok": 0, "failed": 1, "error": f"{type(e).__name__}: {str(e)[:80]}"}
        checks.append(ccheck)
    for e in car_events:
        if e["id"] not in have:
            events.append(e)
            have.add(e["id"])
    # 등급 규칙이 바뀐 뒤에도 같은 달 신호는 다시 이벤트로 만들지 않는다 — 저장된 이벤트의 등급·문장만 지금 규칙으로 맞춘다
    # (10-30: 공장 합계 60% 넘게 감소 A 신설, 현대차 HMGMA 2026-09 이벤트는 B로 저장돼 있었다).
    now_sig = {x["id"]: x for x in (cars or {}).get("signals") or [] if isinstance(x, dict) and x.get("id")}
    for e in events:
        x = now_sig.get(e.get("id"))
        if e.get("kind") == "모델별 판매" and x and x.get("tier") != e.get("tier"):
            e.update(tier=x["tier"], text=f"{x['text']} (IR 엑셀)", retiered=stamp)
    events.sort(key=lambda e: e["detectedAt"], reverse=True)
    failed = [c for c in checks if c["status"] not in ("ok", "unset")]
    return {"schema": SCHEMA, "generatedAt": stamp, "status": "partial" if failed else "complete", "checks": checks,
            "baselineSince": (previous or {}).get("baselineSince") or stamp, "series": series, "kaidaMonths": months,
            "kaida": {"period": latest, "total": months[latest]["total"] if latest else None, "brands": brands, "signals": ksig},
            "carSales": cars,
            "events": events[:600],
            "rules": ["같은 품목·같은 지수 기준·같은 단위 안에서만 비교한다. 지수는 수준이 아니라 기준 시점 대비 변화다.",
                      "'그 달 이후 최고·최저'는 조회 범위(설정 시작월 이후) 안의 사실이다. '역대'는 원 통계표 전체 이력으로 따로 확인한다.",
                      "수출입물가는 원화 기준(환율 효과 포함)이다. 계약통화 기준은 한국은행 원표에서 확인한다.",
                      "KAIDA는 수입 승용차 신규등록(회원사 기준)이다. 테슬라 등 비회원 브랜드는 빠질 수 있다.",
                      "미국 수입(Census)은 한국산 일반수입액(GEN_VAL_MO, 달러 명목)이다. 물량·단가·관세 영향은 따로 확인하고, 월별 변동이 크니 누적·전년 대비로 본다.",
                      "통계 발표 날 보도자료가 함께 나오는 경우가 많다. 같은 수치 기사는 news_check로 먼저 본다.",
                      "조회 실패·미설정은 0건이 아니라 미확인."],
            "confirmedScoops": 0}


def main():
    argparse.ArgumentParser(description="국내 월간 통계(ECOS·KOSIS·KAIDA) 감시(기자 전용 저장소로)").parse_args()
    now = now_kst()
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    import private_store
    previous = None
    if token:
        try:
            previous = private_store.get("kr-stats", token)
        except private_store.StoreError as e:
            print(f"::warning title=kr-stats-state::이전 상태 조회 실패({e}) — 새 달 판단은 다음 실행부터")
    if private_store.late_scheduled_duplicate(previous, now):
        return
    doc = run(cfg, now=now, previous=previous, ecos_key=os.environ.get("ECOS_API_KEY", "").strip(),
              kosis_key=os.environ.get("KOSIS_API_KEY", "").strip(), census_key=os.environ.get("CENSUS_API_KEY", "").strip())
    new_ev = sum(1 for e in doc["events"] if e["detectedAt"] == doc["generatedAt"])
    parts = [f"{c['source']} {c['status']}" + (f" {c.get('ok', 0)}/{c.get('ok', 0) + c.get('failed', 0)}" if "ok" in c else "") +
             (f" 최신 {c.get('latest')}" if c.get("latest") else "") for c in doc["checks"]]
    print(f"::notice title=kr-stats::{' · '.join(parts)} · 계열 {len(doc['series'])} · 새 이벤트 {new_ev}")
    errors = sorted({c.get("error") for c in doc["checks"] if c.get("error")})
    if errors:
        print(f"::notice title=kr-stats-errors::{' | '.join(errors)[:500]}")
    if not token:
        print("::warning title=kr-stats-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if not doc["series"] and not doc["kaidaMonths"] and not (doc.get("carSales") or {}).get("series"):
        sys.exit("모든 질의 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("kr-stats", doc, token)
    print(f"::notice title=kr-stats-push::기자 전용 저장소 전송 HTTP {status}")
    if status == 404:
        print(f"::warning title=kr-stats-token::토큰 거부 또는 배포 전 — {private_store.token_shape(private_store.normalize_token(token))}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
