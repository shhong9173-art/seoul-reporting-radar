"""출입처 공장이 있는 시·군의 고시·공고(새올 전자민원창구) 감시: 제목에 출입처 이름·공장 사업이 나온 새 고시·공고.

- 공장 증설·신설은 회사 발표보다 지자체 고시·공고가 먼저인 경우가 많다: 건설공사 안전점검 수행기관 지정 공고(발주자·공사명),
  환경영향평가 공람, 산업단지 계획 변경, 공유수면 점용·매립, 도시관리계획 결정. 10-30 탐침: 울주군 '건설공사 안전점검 수행기관 지정
  공고[온산 고려아연(주), Ga 2차 …]'(09-14), '[온산 고려아연(주), 정련로 신규 …]'(09-09), 여수시 'GS칼텍스 우순도 공장증설용지 …
  환경영향평가'(2024-11), 당진시 '현대제철㈜ LNG 자가용전기설비 설치사업 환경영향평가(초안)'(2024-11).
- 시·군마다 새올 고시·공고 목록 최신 60건(30건×2쪽)을 받아 처음 보는 관리번호만 본다. 첫 실행은 기준선.
- 등급: 출입처 이름 + 사업 낱말(증설·신설·설치·건설·공장·환경영향평가·매립·산업단지 등) = A, 출입처 이름만 = B,
  출입처 이름 없이 제철소·제련소·산업단지 계획·발전사업 = C. 담배 소매인 지정 같은 생활 공고는 버린다.
- 고시·공고 제목만 본다(첨부 HWP·PDF는 열지 않는다). 사업 규모·내용은 첨부 원문과 회사 확인.
- 해외 IP에서 응답이 느린 시·군(포항 33초·평택 57초)은 75초까지 기다린다. 그래도 시간 초과면 '실패' — 0건이 아니라 미확인.
- 결과는 기자 전용 저장소(kr-local)로만. 공개 로그는 건수만.
"""
from __future__ import annotations

import datetime as dt
import html as htmllib
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "kr_local/v1"
PATH = "/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
LIST = {"method": "selectListOfrNotAncmt", "methodnm": "selectListOfrNotAncmtHomepage", "homepage_pbs_yn": "Y", "subCheck": "Y",
        "ofr_pageSize": "30", "not_ancmt_se_code": "01,02,03,04,05", "initValue": "Y", "countYn": "Y", "list_gubun": "A",
        "jndinm": "OfrNotAncmtEJB", "context": "NTIS", "method_type": ""}
PAGES = 2
TIMEOUT = 75  # 10-30 탐침: 포항 33초·평택 57초 걸려 응답(45초에선 시간 초과)
KEEP_DAYS = 120
KEEP_MAX = 500
SEEN_MAX = 400  # management numbers kept per city

# (시·군, 새올 주소, 이 시·군의 출입처 공장) — 10-30 탐침으로 GitHub 러너에서 목록이 열린 곳 + 느린 곳(시간 초과면 미확인)
CITIES = [
    ("당진시", "https://eminwon.dangjin.go.kr", "현대제철·KG스틸·동국제강"),
    ("아산시", "https://eminwon.asan.go.kr", "현대차"),
    ("여수시", "https://eminwon.yeosu.go.kr", "GS칼텍스·DL케미칼·한화솔루션"),
    ("울주군", "http://eminwon.ulju.ulsan.kr", "고려아연·LS MnM·현대차"),
    ("울산 남구", "https://eminwon.ulsannamgu.go.kr", "현대모비스·고려아연"),
    ("군산시", "https://eminwon.gunsan.go.kr", "세아베스틸·OCI"),
    ("익산시", "http://eminwon.iksan.go.kr", "OCI"),
    ("서산시", "https://eminwon.seosan.go.kr", "현대모비스·한화"),
    ("화성시", "https://eminwon.hscity.go.kr", "기아"),
    ("금산군", "https://eminwon.geumsan.go.kr", "한국타이어"),
    ("대전 대덕구", "https://eminwon.daedeok.go.kr", "한국타이어"),
    ("창녕군", "https://eminwon.cng.go.kr", "넥센타이어"),
    ("곡성군", "http://eminwon.gokseong.go.kr", "금호타이어"),
    ("동해시", "https://eminwon.dh.go.kr", "LS전선"),
    ("진천군", "https://eminwon.jincheon.go.kr", "한화"),
    ("음성군", "https://eminwon.eumseong.go.kr", ""),
    ("영주시", "https://eminwon.yeongju.go.kr", ""),
    ("포항시", "https://eminwon.pohang.go.kr", "포스코·현대제철·동국제강·세아"),
    ("광양시", "https://eminwon.gwangyang.go.kr", "포스코"),
    ("창원시", "https://eminwon.changwon.go.kr", "현대위아·세아창원특수강"),
    ("평택시", "https://eminwon.pyeongtaek.go.kr", "KG모빌리티"),
    ("천안시", "https://eminwon.cheonan.go.kr", "LS일렉트릭"),
    ("양산시", "https://eminwon.yangsan.go.kr", "넥센타이어"),
]

# (출입처, 제목 규칙)
COMPANIES = [
    ("현대차", r"현대자동차|현대차(?!증권)"), ("기아", r"기아(?:\s*\(주\)|㈜|자동차|\s*오토랜드)"), ("현대모비스", r"현대모비스"),
    ("현대위아", r"현대위아"), ("HL만도", r"HL만도|에이치엘만도"), ("한국GM", r"한국지엠|한국GM"), ("KG모빌리티", r"케이지모빌리티|KG모빌리티"),
    ("르노코리아", r"르노코리아"), ("한국타이어", r"한국타이어"), ("넥센타이어", r"넥센타이어"), ("금호타이어", r"금호타이어"),
    ("포스코", r"포스코(?!퓨처엠|인터내셔널|이앤씨|DX|엠텍|스틸리온|모빌리티솔루션)|POSCO"), ("현대제철", r"현대제철"),
    ("KG스틸", r"KG스틸|케이지스틸"), ("세아", r"세아(?:제강|베스틸|창원특수강|홀딩스|씨엠)"), ("동국제강", r"동국제강"),
    ("동국씨엠", r"동국씨엠"), ("고려아연", r"고려아연"), ("영풍", r"영풍\s*(?:석포|\(주\)|㈜)|석포제련소"),
    ("HD현대일렉트릭", r"HD현대일렉트릭|에이치디현대일렉트릭|현대일렉트릭"), ("LS일렉트릭", r"LS일렉트릭|엘에스일렉트릭"),
    ("대한전선", r"대한전선"), ("LS전선", r"LS전선|엘에스전선"), ("LS MnM", r"LS\s*MnM|엘에스엠앤엠|LS엠앤엠"),
    ("두산에너빌리티", r"두산에너빌리티"), ("GS칼텍스", r"GS칼텍스|지에스칼텍스"), ("한화솔루션", r"한화솔루션"),
    ("OCI", r"OCI(?![A-Za-z])|오씨아이"), ("태광", r"태광산업"), ("동성케미칼", r"동성케미칼"), ("DL케미칼", r"DL케미칼|디엘케미칼"),
    ("효성중공업(관련)", r"효성중공업"),
]
PROJECT = re.compile(r"증설|신설|신규|설치|건설|건립|공장|라인|환경영향평가|매립|산업단지|착공|확장|이전|안전점검|사업")
GENERIC = re.compile(r"제철소|제련소|공장\s*(?:증설|신설|설립)|공장증설|산업단지\s*계획|일반산업단지|국가산업단지|산업단지.{0,12}(?:지정|변경|승인)|발전사업|전기사업|발전소\s*(?:건설|설치)")
NOISE = re.compile(r"담배\s*소매|소매인\s*지정|일자리\s*박람회|채용|봉사자|도로명주소")
RULES = [
    "지자체 고시·공고 제목만 본다(첨부 원문은 열지 않음). 사업 규모·내용은 첨부와 회사·지자체 확인.",
    "출입처 이름 + 사업 낱말 = A, 출입처 이름만 = B, 출입처 이름 없이 제철소·제련소·산업단지 계획·발전사업 = C.",
    "건설공사 안전점검 수행기관 지정 공고는 공사가 정해졌다는 뜻이지 착공·완공이 아니다.",
    "첫 실행은 기준선. 시간 초과·실패한 시·군은 0건이 아니라 미확인.",
]


def norm_space(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def cell_text(h):
    return norm_space(htmllib.unescape(re.sub(r"<[^>]+>", " ", h)))


NOTICE_NO = re.compile(r"(?:고시|공고|공시)\s*제?\s*[\d-]+\s*호")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def parse_rows(page):
    """Rows of one 새올 list page. Two layouts (10-30): onclick on each <td> (당진·여수) or an <a onclick> inside each <td>
    (울주·아산). Cells run 번호, 공고번호, 제목, 담당부서, 등록일(, 게재기간, 조회수)."""
    out = []
    for tr in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", page or ""):
        m = re.search(r"searchDetail\(\s*['\"]([0-9A-Za-z_-]+)['\"]\s*\)", tr)
        if not m:
            continue
        cells = [cell_text(c) for c in re.findall(r"<td[^>]*>([\s\S]*?)</td>", tr)]
        i = next((k for k, c in enumerate(cells) if NOTICE_NO.search(c)), None)
        if i is not None and i + 1 < len(cells):
            no, t = cells[i], i + 1
        else:
            # 울산 남구 형식(10-30): 번호, 제목, 담당부서, 등록일, 조회수 — 공고번호 칸이 없다
            no = None
            t = next((k for k, c in enumerate(cells) if c and not re.fullmatch(r"[\d,]+", c) and not DATE.fullmatch(c)), None)
            if t is None:
                continue
        title = cells[t]
        dept = cells[t + 1] if t + 1 < len(cells) and not DATE.fullmatch(cells[t + 1]) and not re.fullmatch(r"[\d,]+", cells[t + 1]) else None
        date = next((c for c in cells[t + 1:] if DATE.fullmatch(c)), None)
        out.append({"mgt": m.group(1), "no": no, "title": title[:200], "dept": dept, "date": date})
    return out


def classify(title):
    if NOISE.search(title):
        return None, []
    hits = [c for c, rx in COMPANIES if re.search(rx, title)]
    if hits:
        return ("A" if PROJECT.search(title) else "B"), hits
    if GENERIC.search(title):
        return "C", []
    return None, []


def detail_url(base, mgt):
    return (f"{base}{PATH}?method=selectOfrNotAncmt&methodnm=selectOfrNotAncmtRegst&not_ancmt_mgt_no={mgt}"
            "&homepage_pbs_yn=Y&subCheck=Y&jndinm=OfrNotAncmtEJB&context=NTIS")


def fetch_page(base, page, post, sleep):
    last = None
    for attempt in range(2):  # 10-30: 포항은 같은 날 33초에 응답하다가 75초도 넘기기도 했다 — 한 번 더
        try:
            r = post(base + PATH, data={**LIST, "pageIndex": str(page)}, headers={**UA, "Referer": base + PATH}, timeout=TIMEOUT)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            return r.text
        except Exception as e:  # noqa: BLE001
            last = e
            sleep(5.0)
    raise last


def fetch_city(city, base, post, sleep):
    """Rows of the first PAGES pages, and a note when a later page failed (the first page's rows are kept)."""
    rows = []
    for page in range(1, PAGES + 1):
        try:
            text = fetch_page(base, page, post, sleep)
        except Exception as e:  # noqa: BLE001
            if page == 1:
                raise
            return rows, f"{page}쪽 {error_kind(e)} — 최신 {len(rows)}건만 봄"
        got = parse_rows(text)
        if not got:
            if page == 1:
                raise RuntimeError("목록 형식 미상")
            break
        rows += got
        sleep(0.5)
    return rows, None


def error_kind(e):
    name = type(e).__name__
    return name if name in ("ConnectTimeout", "ReadTimeout", "ConnectionError", "SSLError", "Timeout") else (str(e)[:40] or name)


def run(*, now, previous=None, post=None, sleep=time.sleep, cities=CITIES):
    if post is None:
        import requests
        post = requests.post
    stamp = now.isoformat(timespec="seconds")
    prev = previous if isinstance(previous, dict) else {}
    seen = {k: list(v) for k, v in (prev.get("seen") or {}).items()}
    old = {x["id"]: x for x in prev.get("items") or [] if isinstance(x, dict) and x.get("id")}
    out = dict(old)
    checks = []

    def one(c):
        city, base, plants = c
        try:
            rows, note = fetch_city(city, base, post, sleep)
            return c, rows, note
        except Exception as e:  # noqa: BLE001
            return c, None, error_kind(e)

    with ThreadPoolExecutor(6) as ex:
        results = list(ex.map(one, cities))
    for (city, base, plants), rows, err in results:
        if rows is None:
            checks.append({"source": city, "status": "failed", "error": err})
            continue
        known = set(seen.get(city) or [])
        baseline = city not in seen  # a city read for the first time is its own baseline
        new = 0
        for r in rows:
            if r["mgt"] in known:
                continue
            known.add(r["mgt"])
            tier, hits = classify(r["title"])
            if not tier:
                continue
            iid = f"local:{city}:{r['mgt']}"
            if iid in out:
                continue
            out[iid] = {"id": iid, "city": city, "plants": plants, "no": r["no"], "title": r["title"], "dept": r["dept"], "date": r["date"],
                        "companies": hits, "company": hits[0] if hits else None, "tier": tier, "url": detail_url(base, r["mgt"]),
                        "listUrl": base + PATH, "firstSeen": stamp, "baseline": baseline, "isNew": not baseline}
            new += 1
        order = [r["mgt"] for r in rows] + [m for m in seen.get(city) or [] if m not in {r["mgt"] for r in rows}]
        seen[city] = order[:SEEN_MAX]
        oldest_seen_reached = any(r["mgt"] in set(prev.get("seen", {}).get(city) or []) for r in rows) or baseline
        notes = [n for n in (err, None if oldest_seen_reached else f"최신 {len(rows)}건 안에 지난 실행 공고가 없음 — 그 사이 공고 일부 미확인") if n]
        checks.append({"source": city, "status": "partial" if notes else "ok", "returned": len(rows), "matched": new,
                       **({"error": "; ".join(notes)} if notes else {})})
    for iid, x in out.items():
        if iid in old and x is old[iid]:
            x["isNew"] = False
    keep_from = (now - dt.timedelta(days=KEEP_DAYS)).isoformat()
    items = sorted((x for x in out.values() if str(x.get("firstSeen")) >= keep_from),
                   key=lambda x: (str(x.get("date") or ""), x["id"]), reverse=True)[:KEEP_MAX]
    failed = [c for c in checks if c["status"] == "failed"]
    status = "failed" if len(failed) == len(checks) else "partial" if any(c["status"] != "ok" for c in checks) else "complete"
    return {"schema": SCHEMA, "generatedAt": stamp, "status": status, "checks": checks, "items": items, "seen": seen,
            "rules": RULES, "cities": len(cities)}


def main():
    import private_store
    now = dt.datetime.now(KST)
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    previous = None
    if token:
        try:
            previous = private_store.get("kr-local", token)
        except private_store.StoreError as e:
            print(f"::warning title=kr-local-state::이전 상태 조회 실패({e}) — 이번 실행은 기준선")
    if private_store.late_scheduled_duplicate(previous, now):
        return
    doc = run(now=now, previous=previous)
    new = [x for x in doc["items"] if x.get("isNew")]
    tiers = {t: sum(1 for x in new if x["tier"] == t) for t in "ABC"}
    ok = [c["source"] for c in doc["checks"] if c["status"] == "ok"]
    bad = [f"{c['source']}({c.get('error') if c['status'] == 'failed' else '일부'})" for c in doc["checks"] if c["status"] != "ok"]
    print(f"::notice title=kr-local::상태 {doc['status']} · 시·군 {len(ok)}/{len(doc['checks'])} 정상 · 새 고시·공고 {tiers} · 보관 {len(doc['items'])}"
          + (f" · 미확인 {', '.join(bad)}" if bad else ""))
    if not token:
        print("::warning title=kr-local-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if doc["status"] == "failed":
        sys.exit("지자체 고시·공고 전체 조회 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("kr-local", doc, token)
    print(f"::notice title=kr-local-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
