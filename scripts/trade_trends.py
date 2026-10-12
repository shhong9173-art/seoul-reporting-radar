"""관세청 공식 HS CSV를 동일 월·HS 범위로 전년 대비 검증.

원본 CSV: scripts/customs.py 결과. 회사 실적, 특정 계약, 기사 인과관계로
해석하거나 다른 품목군과 섞지 않는다.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

FIELDS = ("월", "수출금액(달러)", "수출중량(kg)", "수입금액(달러)", "수입중량(kg)")


def parse_amount(x):
    try:
        value = Decimal(str(x).replace(",", "").strip())
    except InvalidOperation as error:
        raise ValueError(f"관세청 통계 파싱 실패: {x!r}") from error
    if not value.is_finite() or value < 0:
        raise ValueError(f"관세청 통계의 음수·비정상 금액/중량: {x!r}")
    return value


def read_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not set(FIELDS).issubset(reader.fieldnames or []):
            raise ValueError("관세청 CSV의 월·수출입 금액/중량 열이 없음")
        rows = {}
        for row in reader:
            key = row.get("월", "")
            if not re.fullmatch(r"(?:19|20)\d{2}(?:0[1-9]|1[0-2])", key):
                raise ValueError(f"잘못된 월 형식: {key!r}")
            if key in rows:
                raise ValueError(f"월 중복: {key} (중복 합산 금지)")
            rows[key] = {field: parse_amount(row[field]) for field in FIELDS[1:]}
    return rows


def pct(new, old):
    if old == 0:
        return None
    return float((new / old - 1) * 100)


def compare_years(rows, *, target_year):
    year = int(target_year)
    current_months = sorted([month for month in rows if month.startswith(str(year))])
    shared = [(m, str(year-1)+m[4:]) for m in current_months
              if str(year-1)+m[4:] in rows]
    if not shared:
        return {"year": year, "previousYear": year-1, "comparableMonths": [],
                "status": "동일 월 비교자료 없음", "totals": None}
    curr = {f: sum((rows[m][f] for m, _ in shared), Decimal(0)) for f in FIELDS[1:]}
    prev = {f: sum((rows[p][f] for _, p in shared), Decimal(0)) for f in FIELDS[1:]}
    export_dollars = curr["수출금액(달러)"]
    export_weight = curr["수출중량(kg)"]
    prev_dollars = prev["수출금액(달러)"]
    prev_weight = prev["수출중량(kg)"]
    unit_now = export_dollars/export_weight if export_weight else None
    unit_prev = prev_dollars/prev_weight if prev_weight else None
    return {
        "year": year, "previousYear": year-1,
        "comparableMonths": [m[4:] for m, _ in shared],
        "monthsInCurrentYear": len(current_months),
        "status": ("전월이 아닌 전년 동월 비교: 해당 월 교집합만 계산"
                   if len(shared) != len(current_months) else "동일 월 범위 검증"),
        "totals": {
            "currentExportUsd": str(export_dollars),
            "previousExportUsd": str(prev_dollars),
            "exportValueYoYPercent": pct(export_dollars, prev_dollars),
            "currentExportWeightKg": str(export_weight),
            "previousExportWeightKg": str(prev_weight),
            "exportWeightYoYPercent": pct(export_weight, prev_weight),
            "currentUnitValueUsdPerKg": str(unit_now) if unit_now is not None else None,
            "previousUnitValueUsdPerKg": str(unit_prev) if unit_prev is not None else None,
            "unitValueYoYPercent": pct(unit_now, unit_prev)
                                    if unit_now is not None and unit_prev is not None else None,
        }
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("csv_path", help="scripts/customs.py가 저장한 HS별 관세청 월별 CSV")
    p.add_argument("--year", type=int, required=True, help="비교할 연도. 전년도 같은 달만 대조")
    p.add_argument("--output", help="선택 출력 JSON 경로")
    args = p.parse_args()
    input_path = Path(args.csv_path)
    rows = read_rows(input_path)
    result = compare_years(rows, target_year=args.year)
    match = re.search(r"customs_(\d{2,10})_([^_]+)_\d{6}_\d{6}\.csv$", input_path.name)
    result.update({
        "sourceFile": input_path.name,
        "hsCode": match.group(1) if match else "불명: 파일명에서 식별 안 됨",
        "countryFilter": match.group(2) if match else "미확인",
        "basis": "관세청 HS 코드·국가 필터별 월별 수출액(USD)·중량(kg)",
        "warning": "HS 범위·신고시점·잠정치 수정 여부 확인. 단가=수출액/중량이며 계약가격이나 기업별 수출가격을 뜻하지 않음",
    })
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        pth = Path(args.output)
        pth.parent.mkdir(parents=True, exist_ok=True)
        pth.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
