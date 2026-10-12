"""5개 승인 관세청 API를 월별 동일 기간으로 검증 수집한다.

시도별 품목/신성질별/신성질별 국가별/성질별 국가별/종류별은
서로 다른 집계 차원이므로 합산하거나 기업별 실적이라 주장하지 않는다.
입력: GitHub Actions Secret CUSTOMS_API_KEY. 원문/비밀키 로깅 금지.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import requests
from customs import normalize_month, num

KST = timezone(timedelta(hours=9))
BASE = "https://apis.data.go.kr/1220000/"
PORTAL = "https://www.data.go.kr/data/"
# 월별 통계는 대체로 다음 달 중순 공표. 15일 이전에는 전전월만 요청.
REGIONS = {"31": "울산", "44": "충남", "47": "경북"}
MARKETS = {"US": "미국", "CN": "중국"}
HS2 = {"27": "광물성 연료", "72": "철강", "73": "철강제품", "74": "구리", "85": "전기기기", "87": "자동차 등"}
TOPIC = ("자동차", "승용", "차량", "철강", "강판", "강재", "전선", "케이블",
         "변압", "아연", "구리", "석유", "원유", "가스", "전력", "전기", "금속", "화학")
SERVICES = {
    "regional": ("시도별 품목별", "15101641", "sidoitemtrade/getSidoitemtradeList", "천 달러"),
    "newtemper_country": ("신성질별 국가별", "15101607", "nnewtempertrade/getNnewtempertradeList", "달러"),
    "newtemper": ("신성질별", "15101616", "newtempertrade/getNewtempertradeList", "달러"),
    "temper_country": ("성질별 국가별", "15100476", "ntempertrade/getNtempertradeList", "달러"),
    "kind": ("종류별", "15101634", "kindtrade/getKindtradeList", "달러"),
}


def month_for(now):
    previous = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
    if now.day < 16:
        previous = (previous - timedelta(days=1)).replace(day=1)
    return previous.strftime("%Y%m")


def previous_year(month):
    return f"{int(month[:4])-1}{month[4:]}"


def safe_fetch(key, route, params):
    """Prevent requests.HTTPError containing a URL with serviceKey from reaching logs."""
    try:
        response = requests.get(BASE + route,
                                params={"serviceKey": key, **params},
                                timeout=(12, 75))
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except (requests.RequestException, ET.ParseError):
        raise RuntimeError("관세청 XML/API 수신 실패 (인증키 및 URL 비공개)") from None
    if root.findtext(".//resultCode") not in ("00", "0"):
        raise ValueError("관세청 resultCode 오류 (인증키/원문 비공개)")
    rows = root.findall(".//item")
    if not rows:
        raise ValueError("관세청 API 정상 응답이지만 item 없음: 미확인으로 처리")
    return [{child.tag: (child.text or "").strip() for child in node} for node in rows]


def task_specs(month):
    other = previous_year(month)
    tasks = []
    for m in (other, month):
        for region in REGIONS:
            tasks.append(("regional", m, "", region,
                          {"strtYymm": m, "endYymm": m, "sidoCd": region}))
        for d in ("1", "2"):
            standard = {"strtYymm": m, "endYymm": m, "imexTpcd": d}
            # 신성질별: 국가 필터가 없는 API, 전체 국가 자료를 코드별로 합산.
            tasks.append(("newtemper", m, d, "", standard))
            tasks.append(("kind", m, d, "", standard))
            for country in MARKETS:
                tasks.append(("newtemper_country", m, d, country,
                              {**standard, "cntyCd": country}))
                tasks.append(("temper_country", m, d, country,
                              {**standard, "cntyCd": country}))
    return tasks


def convert(service, month, direction, location, records):
    out = []
    assert service in SERVICES
    actual_flow = {"1": "수출", "2": "수입"}
    for r in records:
        if service == "regional":
            period = str(r.get("priodTitle", ""))
            if "총" in period:
                continue
            if period != month[:4]:
                raise ValueError("지역별 API 연도 값과 요청 기간 불일치")
            code = r.get("hsSgn", "")
            if code not in HS2:
                continue
            for flow, field in (("수출", "expUsdAmt"), ("수입", "impUsdAmt")):
                val = num(r.get(field))
                out.append((code, HS2[code], REGIONS[location], flow, val))
            continue
        ym = normalize_month(r.get("year", ""))
        if "총" in str(r.get("year", "")):
            continue
        if ym != month:
            raise ValueError("관세청 집계 기간과 요청 기간 불일치")
        if r.get("impexp") != actual_flow[direction]:
            raise ValueError("관세청 수출입구분이 요청과 다름")
        code = str(r.get("statCd" if service == "kind" else "godsCd", "")).strip()
        label = str(r.get("statCdCntnKor1" if service == "kind" else "godsKor", "")).strip()
        if not code or not label:
            raise ValueError("공식 품목·거래 코드/명칭 누락")
        if service == "newtemper" and not r.get("statCd"):
            raise ValueError("신성질별 국가코드 누락: 전체 합산 근거 없음")
        if service.endswith("_country") and r.get("statCd") != location:
            raise ValueError("국가별 요청과 응답 국가 코드 불일치")
        unit_value = num(r.get("dlr"))
        market = "전 국가 집계" if service == "newtemper" else (
            "전국" if service == "kind" else MARKETS[location])
        out.append((code, label, market, actual_flow[direction], unit_value))
    return out


def aggregate(service, values):
    merged = defaultdict(Decimal)
    names = {}
    for code, label, market, flow, value in values:
        identity = (code, market, flow)
        if service != "newtemper" and identity in merged:
            raise ValueError("관세청 동일 월/코드/국가 중복행: 이중계상 방지")
        merged[identity] += value
        names[identity] = label
    return {k: (names[k], v) for k, v in merged.items()}


def compare(service, current, prior, month, limit=15):
    label, data_id, _, unit = SERVICES[service]
    focus = []
    for (code, market, flow), (name, value) in current.items():
        if service == "regional" and code not in HS2:
            continue
        if service in ("newtemper", "newtemper_country", "temper_country"):
            if not any(word in name for word in TOPIC):
                continue
        old_pair = prior.get((code, market, flow))
        old = old_pair[1] if old_pair else None
        # Missing prior is not 0; never infer a sudden new business from this.
        delta = value - old if old is not None else None
        pct = float((value / old - 1) * 100) if old and old > 0 else None
        focus.append({
            "code": code, "name": name, "market": market, "flow": flow,
            "month": month, "previousMonth": previous_year(month) if old is not None else None,
            "current": format(value, "f"),
            "previous": format(old, "f") if old is not None else None,
            "changePercent": round(pct, 2) if pct is not None else None,
            "comparisonStatus": "전년 동일 월·동일 분류" if old is not None else "전년 수치 미확인",
            "sourceUrl": PORTAL + data_id + "/openapi.do",
        })
    focus.sort(key=lambda x: (
        x["previous"] is None,
        -abs(Decimal(x["current"]) - Decimal(x["previous"] or x["current"])),
        x["name"], x["market"]))
    return {
        "id": service, "name": label, "sourceUrl": PORTAL + data_id + "/openapi.do",
        "unit": unit, "period": month, "previousPeriod": previous_year(month),
        "scope": {
            "regional": "지역별 HS2 품목군. 요청한 단일 월 합계, 응답 priodTitle은 연도만 표시",
            "newtemper_country": "신성질별 8자리 분류·미국/중국. 코드와 국가가 일치하는 개별 행",
            "newtemper": "신성질별 8자리 분류·국가별 응답을 동일 분류 내에서 합산",
            "temper_country": "현행 성질별 5자리 분류·미국/중국. 신성질별과 코드 체계 다름",
            "kind": "수출입 거래 종류별 금액. HS/국가별 자료와 합산 불가",
        }[service],
        "availableRows": len(current),
        "matchedRows": len(focus),
        "rows": focus[:limit],
        "status": "official_public_statistics_not_exclusive",
    }


def build(key, *, now=None, fetcher=safe_fetch):
    if not key:
        raise ValueError("CUSTOMS_API_KEY가 설정되지 않았음")
    today = now or datetime.now(KST)
    month = month_for(today)
    specs = task_specs(month)
    rows = defaultdict(list)
    counts = defaultdict(int)
    # 병렬 수집하되 제한된 호출/동시성. 각 응답은 검증 후 해당 자료에만 귀속.
    def one(spec):
        service, m, direction, location, params = spec
        records = fetcher(key, SERVICES[service][2], params)
        converted = convert(service, m, direction, location, records)
        return service, m, converted, len(records)
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {pool.submit(one, task): task[:4] for task in specs}
        for future in as_completed(jobs):
            service, m, direction, location = jobs[future]
            try:
                _, _, data, n = future.result()
            except (ValueError, RuntimeError) as exc:
                raise RuntimeError(f"{service}/{m}/{direction}/{location}: {exc}") from None
            rows[(service, m)].extend(data)
            counts[(service, m)] += n
    result = []
    for service in SERVICES:
        current = aggregate(service, rows[(service, month)])
        prior = aggregate(service, rows[(service, previous_year(month))])
        if not current or not prior:
            raise ValueError(f"{service}: 비교 가능한 원본 자료 자체가 누락됨")
        item = compare(service, current, prior, month)
        item["rawRecordsCurrent"] = counts[(service, month)]
        item["rawRecordsPriorYear"] = counts[(service, previous_year(month))]
        result.append(item)
    return {
        "generatedAt": today.isoformat(timespec="seconds"),
        "status": "official_customs_five_statistical_context",
        "period": month, "previousPeriod": previous_year(month),
        "scopeWarning": "5개 통계는 집계 차원·분류 정의·단위가 서로 다름. 중복 합산과 회사별 실적 귀속 금지. 미보도/단독 판정 아님.",
        "services": result,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="digests/customs_five_latest.json")
    args = parser.parse_args()
    key = os.getenv("CUSTOMS_API_KEY", "").strip()
    if not key:
        print("CUSTOMS_API_KEY 미설정: 기존 통계 보존")
        return
    result = build(key)
    p = Path(args.output)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(p)
    print("관세청 독립 집계 5개 API 응답 검증, 비교월", result["period"],
          " / ".join(f"{s['id']}={s['rawRecordsCurrent']}원문행/{len(s['rows'])}표시행"
                   for s in result["services"]))


if __name__ == "__main__":
    main()
