"""관세청 품목별·국가별 수출입실적 조회 (공공데이터포털 API).

필요한 것: 공공데이터포털(data.go.kr)에서 '관세청_품목별 국가별 수출입실적' 활용신청 후 받은 일반 인증키(Decoding 키)를
환경변수 CUSTOMS_API_KEY 에.

실행 예:
  python scripts/customs.py --hs 8504 --start 202301 --end 202609
  python scripts/customs.py --hs 8544 --start 202501 --end 202609 --country US
결과는 화면 표 + data/customs_<hs>_<기간>.csv 로 저장. 금액 단위는 달러(USD), 중량은 kg.

주의
- HS 코드는 무역통계(tradedata.go.kr)에서 품목 범위를 다시 확인할 것. 앞자리가 짧을수록 넓게 묶인다.
- API는 한 번에 최대 1년 범위만 받아서, 긴 기간은 1년씩 끊어 부른다.
- 이 숫자(HS 기준)는 산업부·협회 품목군 숫자와 분류가 달라 기사 한 문장에 섞지 않는다.
- 첫 실행 때 응답 항목 이름이 바뀌었으면 --raw 로 원문을 찍어 확인할 것.
"""
import argparse
import csv
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

import requests

URL = "https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"
ROOT = Path(__file__).resolve().parent.parent


def month_add(yyyymm, n):
    y, m = int(yyyymm[:4]), int(yyyymm[4:])
    m += n
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f"{y:04d}{m:02d}"


def chunks(start, end):
    cur = start
    while cur <= end:
        stop = min(month_add(cur, 11), end)
        yield cur, stop
        cur = month_add(stop, 1)


def fetch(k, hs, start, end, country, raw=False):
    params = {"serviceKey": k, "strtYymm": start, "endYymm": end, "hsSgn": hs}
    if country:
        params["cntyCd"] = country
    r = requests.get(URL, params=params, timeout=60)
    r.raise_for_status()
    if raw:
        print(r.text[:3000])
    root = ET.fromstring(r.content)
    code = root.findtext(".//resultCode")
    if code not in ("00","0"):
        raise RuntimeError(f"관세청 API 오류/응답 형식 미확인 {code}: {root.findtext('.//resultMsg')}")
    return [{c.tag: (c.text or "").strip() for c in item} for item in root.iter("item")]


def num(x):
    if x is None or str(x).strip()=="":
        raise ValueError("관세청 원자료 수치가 누락됨")
    try:
        n=Decimal(str(x).replace(",", ""))
    except (InvalidOperation,ValueError,TypeError) as exc:
        raise ValueError(f"관세청 원자료 숫자 파싱 실패: {x!r}") from exc
    if not n.is_finite() or n<0:
        raise ValueError(f"관세청 비정상 금액·중량: {x!r}")
    return n

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hs", required=True, help="HS 코드 (2~10자리)")
    ap.add_argument("--start", required=True, help="YYYYMM")
    ap.add_argument("--end", required=True, help="YYYYMM")
    ap.add_argument("--country", default="", help="국가 코드 (US, CN, JP ...). 비우면 전체")
    ap.add_argument("--raw", action="store_true", help="API 원문 앞부분 출력")
    a = ap.parse_args()

    if not re.fullmatch(r"(?:19|20)\d{2}(?:0[1-9]|1[0-2])", a.start) or not re.fullmatch(r"(?:19|20)\d{2}(?:0[1-9]|1[0-2])", a.end) or a.start>a.end:
        ap.error("연월 YYYYMM 범위 오류")
    if not re.fullmatch(r"\d{2,10}", a.hs):
        ap.error("HS 코드는 숫자 2~10자리만 입력")
    k = os.environ.get("CUSTOMS_API_KEY", "").strip()
    if not k:
        sys.exit("CUSTOMS_API_KEY 환경변수가 없다. data.go.kr 에서 인증키를 받아 넣어줘.")

    items = []
    for s, e in chunks(a.start, a.end):
        items += fetch(k, a.hs, s, e, a.country, a.raw)

    # 월별 합계 (총계 줄은 빼고, 같은 달 여러 세부 HS 줄은 더한다)
    by_month = defaultdict(lambda: [Decimal(0), Decimal(0), Decimal(0), Decimal(0)])
    for it in items:
        ym = it.get("year", "")
        if not ym or "총" in ym:
            continue
        if not re.fullmatch(r"\d{6}", ym):
            raise ValueError(f"월별 원자료 기간 형식 오류: {ym!r}")
        if any(k not in it for k in ("expDlr","expWgt","impDlr","impWgt")):
            raise ValueError(f"관세청 API 응답 수치 열 누락: {sorted(it)}")
        v = by_month[ym]
        v[0] += num(it["expDlr"])
        v[1] += num(it["expWgt"])
        v[2] += num(it["impDlr"])
        v[3] += num(it["impWgt"])

    out = ROOT / "data" / f"customs_{a.hs}_{a.country or 'ALL'}_{a.start}_{a.end}.csv"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["월", "수출금액(달러)", "수출중량(kg)", "수입금액(달러)", "수입중량(kg)"])
        for ym in sorted(by_month):
            w.writerow([ym, *[format(x,"f") for x in by_month[ym]]])

    print(f"HS {a.hs} {a.country or '전체 국가'} {a.start}~{a.end}")
    print(f"{'월':<10}{'수출(만달러)':>14}{'수입(만달러)':>14}")
    yearly = defaultdict(lambda: Decimal(0))
    for ym in sorted(by_month):
        e, _, i, _ = by_month[ym]
        yearly[ym[:4]] += e
        print(f"{ym:<10}{e/Decimal(10000):>14,.0f}{i/Decimal(10000):>14,.0f}")
    print("\n연도별 수출 합계(만달러, 부분 연도는 그 기간만):")
    for y in sorted(yearly):
        print(f"  {y}: {yearly[y]/Decimal(10000):,.0f}")
    print(f"\n저장: {out}")


if __name__ == "__main__":
    main()