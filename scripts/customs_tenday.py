"""관세청 주요품목 10일 단위 잠정치. 발표된 *누적치*만 저장한다.

출처: 공공데이터포털 15157908(수출), 15157901(수입).
일별·개별 기업별·HS10별 통계가 아니며 1~10일, 1~20일, 1~말일 누적이다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import requests

from customs import num

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
BASE = "https://apis.data.go.kr/1220000"
SOURCES = {
    "exp_item": {
        "endpoint": "prlstMmUtPrviExpAcrs",
        "dataset": "15157908",
        "label": "수출 주요품목별 10일 단위 잠정치",
        # 관세청 공표 주요품목 순서. 반드시 번호 순서를 바꾸지 않는다.
        "names": ["총수출", "반도체", "철강제품", "승용차", "석유제품",
                  "무선통신기기", "선박", "자동차부품", "컴퓨터주변기기",
                  "정밀기기", "가전제품"],
        "focus": ["철강제품", "승용차", "자동차부품", "석유제품"],
    },
    "imp_item": {
        "endpoint": "prlstMmUtPrviImpAcrs",
        "dataset": "15157901",
        "label": "수입 주요품목별 10일 단위 잠정치",
        "names": ["총수입", "반도체", "원유", "기계류", "가스",
                  "반도체제조장비", "정밀기기", "석유제품",
                  "무선통신기기", "승용차", "석탄"],
        "focus": ["원유", "기계류", "가스", "석유제품", "승용차", "석탄"],
    },
}


def previous_month(yyyymm: str) -> str:
    y, m = int(yyyymm[:4]), int(yyyymm[4:])
    if m == 1:
        return f"{y-1}12"
    return f"{y}{m-1:02d}"


def months_to_check(today: datetime) -> list[str]:
    current = today.strftime("%Y%m")
    prior = previous_month(current)
    return [f"{int(prior[:4])-1}{prior[4:]}", f"{int(current[:4])-1}{current[4:]}",
            prior, current]


def cutoff_for(label: str) -> int:
    clean = (label or "").strip().replace(" ", "")
    if clean in ("01~10", "1~10"):
        return 10
    if clean in ("01~20", "1~20"):
        return 20
    if clean in ("01~말일", "1~말일") or re.fullmatch(r"0?1~(?:28|29|30|31)", clean):
        return 99
    raise ValueError(f"10일 잠정치 기간 구분이 알려진 형식이 아님: {clean!r}")


def parse(xml: bytes | str, series: str, month: str) -> list[dict]:
    source = SOURCES[series]
    root = ET.fromstring(xml)
    code = root.findtext(".//resultCode")
    if code not in ("00", "0"):
        raise ValueError(f"관세청 잠정치 응답 실패: 코드 {code!r} (비밀키 및 전문은 기록하지 않음)")
    records = []
    seen = set()
    for node in root.findall(".//item"):
        item = {x.tag: (x.text or "").strip() for x in node}
        period = item.get("priodMon", "").replace(".", "")
        if period != month:
            raise ValueError(f"요청 월과 잠정치 응답 월 불일치: {month} / {period}")
        label = item.get("priodDt", "")
        cutoff = cutoff_for(label)
        if cutoff in seen:
            raise ValueError(f"동일 월·구간 중복: {series}, {month}, {cutoff}")
        seen.add(cutoff)
        amounts = []
        for i, name in enumerate(source["names"]):
            field = f"itemUsdAmt{i:02d}"
            if field not in item:
                raise ValueError(f"잠정치 필수 항목 누락: {field}")
            value = num(item[field])
            amounts.append({"name": name, "amountKUsd": format(value, "f")})
        if sum(Decimal(x["amountKUsd"]) for x in amounts[1:]) > Decimal(amounts[0]["amountKUsd"]):
            raise ValueError(f"10대 품목의 합이 전체 통계를 초과: {series} {month}/{cutoff}")
        records.append({"series": series, "month": month, "cutoff": cutoff,
                        "periodLabel": label, "items": amounts})
    return records


def fetch(api_key: str, series: str, month: str) -> list[dict]:
    endpoint = SOURCES[series]["endpoint"]
    path = f"/{endpoint}/get{endpoint[0].upper()}{endpoint[1:]}"
    try:
        response = requests.get(BASE + path, params={
            "serviceKey": api_key, "strtYymm": month, "endYymm": month
        }, timeout=50)
        response.raise_for_status()
    except requests.HTTPError as exc:
        # Report only HTTP status and public gateway error code, never the URL/key.
        try:
            gw_code = ET.fromstring(exc.response.content).findtext(".//returnReasonCode")
        except (ET.ParseError, TypeError):
            gw_code = None
        status = exc.response.status_code
        raise RuntimeError(f"{series} {month}: 관세청 API HTTP {status} / gateway {gw_code or 'unknown'} (URL 비공개)") from None
    except requests.RequestException:
        raise RuntimeError(f"{series} {month}: API 네트워크 오류 (URL 비공개)") from None
    return parse(response.content, series, month)


def yoy_percent(current: str, previous: str | None):
    if previous is None or Decimal(previous) == 0:
        return None
    return float((Decimal(current) / Decimal(previous) - 1) * 100)


def build(api_key: str, *, today: datetime | None = None, fetch_fn=fetch) -> dict:
    if not api_key:
        raise ValueError("CUSTOMS_API_KEY 미설정")
    now = today or datetime.now(KST)
    periods = months_to_check(now)
    observed = []
    for series in SOURCES:
        for month in periods:
            observed.extend(fetch_fn(api_key, series, month))
    lookup = {(x["series"], x["month"], x["cutoff"]): x for x in observed}
    if len(lookup) != len(observed):
        raise ValueError("잠정치 기간 중복 기록")
    selected = []
    for series, source in SOURCES.items():
        recent = [row for row in observed if row["series"] == series and
                  row["month"] in periods[-2:]]
        if not recent:
            raise ValueError(f"{series}: 최근 두 달의 관세청 잠정치 응답이 없음")
        latest = max(recent, key=lambda r: (r["month"], r["cutoff"]))
        old_month = f"{int(latest['month'][:4])-1}{latest['month'][4:]}"
        previous = lookup.get((series, old_month, latest["cutoff"]))
        prior_amounts = {x["name"]: x["amountKUsd"] for x in previous["items"]} if previous else {}
        for item in latest["items"]:
            if item["name"] not in source["focus"]:
                continue
            old = prior_amounts.get(item["name"])
            selected.append({
                "series": series, "label": source["label"],
                "item": item["name"], "month": latest["month"],
                "cutoff": latest["cutoff"], "periodLabel": latest["periodLabel"],
                "amountKUsd": item["amountKUsd"],
                "priorYearMonth": old_month if old is not None else None,
                "priorYearAmountKUsd": old,
                "yoyPercent": yoy_percent(item["amountKUsd"], old),
                "comparisonStatus": "전년 동일 누적구간" if old is not None else "비교 기준값 미확인",
                "sourceUrl": f"https://www.data.go.kr/data/{source['dataset']}/openapi.do",
            })
    return {
        "generatedAt": now.isoformat(timespec="seconds"),
        "status": "official_provisional_10day_context_not_exclusive",
        "unit": "천 달러 (thousand USD)",
        "scopeWarning": "1~10일·1~20일·1~말일의 누적 금액. 일별 증감/HS세번/개별 기업 수출입 실적이 아님. 다른 관세청 집계와 합산 금지.",
        "observed": observed, "focus": selected,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="digests/customs_tenday_latest.json")
    args = parser.parse_args()
    key = os.getenv("CUSTOMS_API_KEY", "").strip()
    if not key:
        print("관세청 인증키 미설정: 기존 잠정치 자료 보존, 수집 생략")
        return
    result = build(key)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)
    print(f"관세청 10일 잠정치 공식 응답 {len(result['observed'])}개 구간, 취재 참고 {len(result['focus'])}개 품목")


if __name__ == "__main__":
    main()
