"""출입처 DART 공시 감시.

watchlist.txt 의 회사들이 최근 N일 낸 공시를 모아 digests/YYYY-MM-DD.md 로 저장한다.
수주·증설·지분 변동처럼 기사 되는 공시는 ★ 표시를 달아 위로 올린다.
이미 본 공시(data/seen.txt)는 '새 공시'에서 빠진다.

필요한 것: DART OpenAPI 인증키(opendart.fss.or.kr 에서 무료 발급) 를 환경변수 DART_API_KEY 에.
선택: 폰 알림을 받고 싶으면 ntfy 앱에서 정한 토픽 이름을 환경변수 NTFY_TOPIC 에.

실행:  python scripts/dart_watch.py            (기본 최근 3일)
       python scripts/dart_watch.py --days 7
"""
import argparse
import datetime as dt
import io
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DIGESTS = ROOT / "digests"
API = "https://opendart.fss.or.kr/api"
KST = dt.timezone(dt.timedelta(hours=9))

# (보고서명에 들어 있으면, 붙일 표시, 우선순위: 숫자가 작을수록 위)
FLAGS = [
    ("단일판매", "★수주", 1),
    ("공급계약", "★수주", 1),
    ("신규시설투자", "★증설", 1),
    ("유형자산양수", "★자산인수", 1),
    ("타법인주식및출자증권취득", "★지분인수", 1),
    ("타법인주식및출자증권처분", "★지분매각", 1),
    ("영업양수", "★영업양수도", 1),
    ("영업양도", "★영업양수도", 1),
    ("회사분할", "★분할", 1),
    ("회사합병", "★합병", 1),
    ("최대주주변경", "★최대주주", 1),
    ("대량보유상황보고", "★지분변동", 2),
    ("특정증권등소유상황보고", "★임원지분", 2),
    ("소송등의제기", "★소송", 2),
    ("유상증자", "★증자", 2),
    ("자기주식", "★자사주", 3),
    ("대규모내부거래", "★내부거래", 3),
    ("영업실적등에대한전망", "★실적전망", 3),
    ("매출액또는손익구조", "★실적변동", 3),
    ("연결재무제표기준영업(잠정)실적", "★잠정실적", 3),
    ("영업(잠정)실적", "★잠정실적", 3),
    ("생산중단", "★생산중단", 1),
    ("영업정지", "★영업정지", 1),
    ("횡령", "★횡령배임", 1),
    ("배임", "★횡령배임", 1),
]


def key():
    k = os.environ.get("DART_API_KEY", "").strip()
    if not k:
        sys.exit("DART_API_KEY 환경변수가 없다. opendart.fss.or.kr 에서 인증키를 받아 넣어줘.")
    return k


def load_watchlist():
    groups, cur = {}, "기타"
    for line in (ROOT / "watchlist.txt").read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("[") and s.endswith("]"):
            cur = s[1:-1]
            continue
        groups.setdefault(cur, []).append(s)
    return groups


def load_corp_codes(k):
    """DART 전체 회사 고유번호 표를 받아 {회사명: [(corp_code, stock_code), ...]} 로 만든다. 하루 한 번만 받는다."""
    DATA.mkdir(exist_ok=True)
    cache = DATA / "corpcode.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < 86400:
        return json.loads(cache.read_text(encoding="utf-8"))
    r = requests.get(f"{API}/corpCode.xml", params={"crtfc_key": k}, timeout=60)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        xml = z.read(z.namelist()[0])
    table = {}
    for el in ET.fromstring(xml).iter("list"):
        name = (el.findtext("corp_name") or "").strip()
        table.setdefault(name, []).append(
            [(el.findtext("corp_code") or "").strip(), (el.findtext("stock_code") or "").strip()]
        )
    cache.write_text(json.dumps(table, ensure_ascii=False), encoding="utf-8")
    return table


def pick_code(table, name):
    rows = table.get(name)
    if not rows:
        return None
    listed = [r for r in rows if r[1]]
    candidate_codes = {r[0] for r in (listed or rows) if r[0]}
    return next(iter(candidate_codes)) if len(candidate_codes) == 1 else None


def filings(k, corp_code, bgn, end):
    out, page = [], 1
    while True:
        r = requests.get(
            f"{API}/list.json",
            params={"crtfc_key": k, "corp_code": corp_code, "bgn_de": bgn, "end_de": end,
                    "page_no": page, "page_count": 100},
            timeout=30,
        )
        r.raise_for_status()
        j = r.json()
        if j.get("status") == "013":  # 조회 결과 없음
            return out
        if j.get("status") != "000":
            raise RuntimeError(f"DART 오류 {j.get('status')}: {j.get('message')}")
        out += j.get("list", [])
        if page >= int(j.get("total_page", 1)):
            return out
        if page >= 30:
            raise RuntimeError("DART 공시 목록 페이지가 30개를 넘어 수집을 중단합니다.")
        page += 1
        time.sleep(0.2)


def flag_of(report_nm):
    nm = report_nm.replace(" ", "")
    best = None
    for word, tag, pri in FLAGS:
        if word in nm and (best is None or pri < best[1]):
            best = (tag, pri)
    return best or ("", 9)


def notify(text):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        return
    try:
        requests.post(f"https://ntfy.sh/{topic}", data=text.encode("utf-8"), timeout=15)
    except requests.RequestException as e:
        print("알림 실패:", e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3, help="달력 기준 역산 일수(1~14일)")
    a = ap.parse_args()
    if not 1 <= a.days <= 14:
        ap.error("--days는 1~14일이어야 합니다.")

    k = key()
    today = dt.datetime.now(KST).date()
    bgn = (today - dt.timedelta(days=a.days)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")

    table = load_corp_codes(k)
    seen_path = DATA / "seen.txt"
    seen = set(seen_path.read_text(encoding="utf-8").split()) if seen_path.exists() else set()

    rows, missing = [], []
    for group, names in load_watchlist().items():
        for name in names:
            code = pick_code(table, name)
            if not code:
                missing.append(name)
                continue
            for f in filings(k, code, bgn, end):
                tag, pri = flag_of(f["report_nm"])
                rows.append({**f, "group": group, "tag": tag, "pri": pri, "new": f["rcept_no"] not in seen})
            time.sleep(0.2)

    rows.sort(key=lambda x: (x["pri"], -int(x["rcept_dt"])))  # 중요한 것 먼저, 같은 급이면 최신 먼저

    lines = [f"# 출입처 공시 {bgn}~{end}", "",
             f"생성 {dt.datetime.now(KST):%Y-%m-%d %H:%M} KST · 총 {len(rows)}건 · 새 공시 {sum(r['new'] for r in rows)}건", ""]
    flagged = [r for r in rows if r["tag"]]
    lines += ["## ★ 우선 확인 공시 (공개자료·단독 아님)", "", "★는 서류 유형에 따른 우선 확인 표식이며 미보도·단독 판정은 아닙니다.", ""]
    if not flagged:
        lines.append("없음")
    for r in flagged:
        lines.append(_line(r))
    lines += ["", "## 나머지 (묶음별)", ""]
    for r in sorted([r for r in rows if not r["tag"]], key=lambda x: (x["group"], x["rcept_dt"])):
        lines.append(_line(r))
    if missing:
        lines += ["", "## DART에서 못 찾은 이름 (watchlist.txt 고칠 것)", "", ", ".join(missing)]

    DIGESTS.mkdir(exist_ok=True)
    out = DIGESTS / f"{today:%Y-%m-%d}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (DIGESTS / "latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    digest = {
        "generatedAt": dt.datetime.now(KST).isoformat(timespec="seconds"),
        "date": today.isoformat(), "rangeStart": bgn, "rangeEnd": end,
        "totalCount": len(rows), "newCount": sum(r["new"] for r in rows),
        "flaggedCount": len(flagged), "missingCompanies": missing,
        "classification": "공개자료·단독 여부 미확정",
        "items": [
            {"company": r["corp_name"], "group": r["group"],
             "report": r["report_nm"].strip(), "published": r["rcept_dt"],
             "receiptNo": r["rcept_no"], "tag": r["tag"],
             "priority": r["pri"], "isNew": r["new"],
             "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r['rcept_no']}"}
            for r in rows
        ],
    }
    (DIGESTS / "latest.json").write_text(
        json.dumps(digest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    seen |= {r["rcept_no"] for r in rows}
    seen_path.write_text("\n".join(sorted(seen)) + "\n", encoding="utf-8")
    print(f"저장: {out} ({len(rows)}건, ★ {len(flagged)}건)")
    if missing:
        print("못 찾은 이름:", ", ".join(missing))

    hot = [r for r in flagged if r["new"]]
    if hot:
        notify("오늘 출입처 ★공시\n" + "\n".join(f"{r['tag']} {r['corp_name']} {r['report_nm'].strip()}" for r in hot[:15]))


def _line(r):
    new = "🆕 " if r["new"] else ""
    url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r['rcept_no']}"
    tag = f"{r['tag']} " if r["tag"] else ""
    return f"- {new}{tag}[{r['group']}] {r['corp_name']} | {r['report_nm'].strip()} | {r['rcept_dt']} | 접수 {r['rcept_no']} | {url}"


if __name__ == "__main__":
    main()