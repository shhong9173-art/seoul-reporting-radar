"""미 연방 규제 의견서 감시(regulations.gov): 출입처 명의로 제출된 의견서.

- 회사 영문명을 큰따옴표로 묶어 의견서(comments)를 최신순으로 찾고, 제목의 제출자
  ("Comment from Hyundai Motor Group", "Comment submitted by Hyundai Motor America")가 출입처일 때만 남긴다.
  다른 단체 의견서가 출입처를 인용한 것은 제외한다.
- 새로 잡힌 의견서는 도켓 제목·첨부 파일 주소를 덧붙인다(호출 예산 안에서).
- 결과는 기자 전용 저장소(us-comments)로만 보낸다. 공개 로그에는 건수만.
- 조회 실패는 0건이 아니다(질의별 상태를 남긴다).
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

API = "https://api.regulations.gov/v4"
KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "us_comments/v1"
LOOKBACK_DAYS = 180
NEW_DAYS = 14
UA = "Mozilla/5.0 (seoul-reporting-radar)"

# (출입처, 검색 문구, 제출자 판정 정규식)
COMPANIES = [
    ("현대차", "Hyundai Motor", r"hyundai motor"),
    ("기아", "Kia America", r"\bkia\b"),
    ("기아", "Kia Corporation", r"\bkia\b"),
    ("제네시스(현대차)", "Genesis Motor", r"genesis motor"),
    ("현대모비스", "Hyundai Mobis", r"hyundai mobis"),
    ("HL만도", "HL Mando", r"\bmando\b"),
    ("한국타이어", "Hankook Tire", r"hankook"),
    ("넥센타이어", "Nexen Tire", r"nexen"),
    ("금호타이어", "Kumho Tire", r"kumho(?!\s*(?:petrochemical|p&b))"),
    ("포스코", "POSCO", r"\bposco\b"),
    ("현대제철", "Hyundai Steel", r"hyundai steel"),
    ("세아제강", "SeAH Steel", r"\bseah\b"),
    ("동국제강·동국씨엠", "Dongkuk", r"dongkuk"),
    ("고려아연", "Korea Zinc", r"korea zinc"),
    ("HD현대일렉트릭", "HD Hyundai Electric", r"hd hyundai electric|hyundai power transformers"),
    ("LS일렉트릭", "LS Electric", r"\bls electric\b"),
    ("LS전선", "LS Cable", r"\bls cable\b|ls greenlink"),
    ("대한전선", "Taihan", r"taihan"),
    ("두산에너빌리티", "Doosan Enerbility", r"doosan"),
    ("효성중공업", "Hyosung Heavy Industries", r"hyosung"),
    ("한화솔루션", "Hanwha Qcells", r"hanwha|qcells|q cells"),
    ("OCI", "OCI Holdings", r"\boci\b|mission solar"),
    ("GS칼텍스", "GS Caltex", r"gs caltex"),
    # 11-01 기자 명시: 석유화학·정유
    ("LG화학", "LG Chem", r"\blg chem\b"), ("롯데케미칼", "Lotte Chemical", r"lotte chemical"),
    ("금호석유화학", "Kumho Petrochemical", r"kumho petrochemical"), ("S-OIL", "S-Oil", r"\bs-oil\b"),
    ("HD현대오일뱅크", "Hyundai Oilbank", r"hyundai oil ?bank"), ("SK이노베이션", "SK Innovation", r"\bsk innovation"),
    ("KG모빌리티", "KG Mobility", r"kg mobility"),
]
SUBMITTER = re.compile(r"^\s*comments?\s+(?:from|submitted\s+by|by)\s+(.+?)\s*$", re.I)


class Budget:
    def __init__(self, n):
        self.left = n

    def take(self):
        if self.left <= 0:
            return False
        self.left -= 1
        return True


def call(path, params, key, *, get=None, budget=None, sleep=time.sleep):
    if budget is not None and not budget.take():
        return "skipped", None
    if get is None:
        import requests
        get = requests.get
    try:
        r = get(f"{API}{path}", params={**params, "api_key": key}, headers={"User-Agent": UA, "Accept": "application/json"},
                timeout=30)
    except Exception as e:
        return "failed", type(e).__name__
    finally:
        sleep(1.2)
    if r.status_code == 429:
        return "failed", "HTTP 429 호출 한도"
    if r.status_code != 200:
        return "failed", f"HTTP {r.status_code}"
    try:
        return "ok", r.json()
    except ValueError:
        return "failed", "JSON 아님"


def submitter_of(title):
    m = SUBMITTER.match(str(title or ""))
    return m.group(1) if m else None


# 11-01 석유화학·정유 6곳을 더한 첫 실행(#532 병합 뒤)이 그 회사들의 지난 의견서(6월 롯데케미칼 3건)를 새것으로 저장했다.
# 그날 처음 본, 14일보다 오래된 그 회사 의견서는 기준선으로 고쳐 둔다.
ADDED_1101 = {"LG화학", "롯데케미칼", "금호석유화학", "S-OIL", "HD현대오일뱅크", "SK이노베이션"}


def collect(key, *, now, previous=None, get=None, sleep=time.sleep, budget=None):
    # DEMO_KEY allows about 30 calls an hour per IP; a free api.data.gov key allows 1,000.
    budget = budget or Budget(int(os.environ.get("REGS_CALL_BUDGET", "28" if key == "DEMO_KEY" else "150")))
    since = (now - dt.timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    prev = {x["id"]: x for x in (previous or {}).get("items", []) if isinstance(x, dict) and x.get("id")}
    dockets = dict((previous or {}).get("docketTitles") or {})
    checks, found = [], {}
    # 감시 도중 더한 검색 문구: 그 문구의 첫 읽기는 기준선(지난 의견서가 새것으로 뜨지 않게). 첫 실행 전체는 원래대로 isNew로 다룬다.
    known = {c.get("phrase") for c in (previous or {}).get("checks") or [] if c.get("status") == "ok"}
    new_since = (now - dt.timedelta(days=NEW_DAYS)).strftime("%Y-%m-%d")
    for company, phrase, pattern in COMPANIES:
        fresh_phrase = bool(known) and phrase not in known
        status, body = call("/comments", {"filter[searchTerm]": f'"{phrase}"', "filter[postedDate][ge]": since,
                                          "page[size]": 50, "sort": "-postedDate"}, key, get=get, budget=budget, sleep=sleep)
        if status != "ok":
            checks.append({"company": company, "phrase": phrase, "status": status, **({"error": body} if body else {})})
            continue
        rows = body.get("data") or []
        own = 0
        for d in rows:
            a = d.get("attributes") or {}
            who = submitter_of(a.get("title"))
            if not who or not re.search(pattern, who, re.I):
                continue  # anonymous, or another organisation citing the company
            cid = d.get("id")
            own += 1
            item = found.get(cid) or {
                "id": cid, "company": company, "submitter": who, "agency": a.get("agencyId"),
                "docketId": cid.rsplit("-", 1)[0] if cid and "-" in cid else None,
                "postedDate": str(a.get("postedDate") or "")[:10], "title": a.get("title"),
                "url": f"https://www.regulations.gov/comment/{cid}",
                "firstSeen": prev.get(cid, {}).get("firstSeen") or now.isoformat(timespec="seconds"),
            }
            old = prev.get(cid)
            if old is not None:
                repair = (company in ADDED_1101 and str(old.get("firstSeen", "")).startswith("2026-11-01")
                          and "baseline" not in old and item["postedDate"] < new_since)
                item["baseline"] = bool(old.get("baseline")) or repair
            else:
                item["baseline"] = fresh_phrase and item["postedDate"] < new_since
            for k in ("docketTitle", "attachments", "excerpt"):
                if prev.get(cid, {}).get(k):
                    item[k] = prev[cid][k]
            found[cid] = item
        checks.append({"company": company, "phrase": phrase, "status": "ok", "returned": len(rows), "own": own})
    # Enrich new items within budget: docket title and attachment links.
    for item in sorted(found.values(), key=lambda x: x["postedDate"], reverse=True):
        did = item.get("docketId")
        if did and did not in dockets:
            st, body = call(f"/dockets/{did}", {}, key, get=get, budget=budget, sleep=sleep)
            if st == "ok":
                dockets[did] = ((body.get("data") or {}).get("attributes") or {}).get("title")
        if did in dockets:
            item["docketTitle"] = dockets[did]
        if "attachments" not in item:
            st, body = call(f"/comments/{item['id']}", {"include": "attachments"}, key, get=get, budget=budget, sleep=sleep)
            if st == "ok":
                attrs = ((body.get("data") or {}).get("attributes") or {})
                text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(attrs.get("comment") or ""))).strip()
                item["excerpt"] = text[:400]
                files = []
                for inc in body.get("included") or []:
                    for f in ((inc.get("attributes") or {}).get("fileFormats") or []):
                        if f.get("fileUrl"):
                            files.append(f["fileUrl"])
                item["attachments"] = files[:5]
    items = sorted(found.values(), key=lambda x: (x["postedDate"], x["id"]), reverse=True)
    for x in items:
        x["isNew"] = x["postedDate"] >= new_since or (x["id"] not in prev and not x.get("baseline"))
    failed = [c for c in checks if c["status"] != "ok"]
    return {
        "schema": SCHEMA, "generatedAt": now.isoformat(timespec="seconds"), "lookbackDays": LOOKBACK_DAYS,
        "status": "partial" if failed else "complete", "checks": checks, "items": items,
        "docketTitles": {k: v for k, v in dockets.items() if v},
        "keyType": "DEMO_KEY" if key == "DEMO_KEY" else "api.data.gov",
        "rules": ["제출자가 제목에 출입처로 적힌 의견서만. 다른 단체가 출입처를 인용한 의견서는 제외.",
                  "의견서는 회사의 정책 요청이다. 규정 확정·회사 사업 변경이 아니다. 본문(첨부 PDF)을 열어 수치·문구를 확인한다.",
                  "질의 실패·예산 초과는 0건이 아니라 미확인."],
        "confirmedScoops": 0,
    }


def main():
    ap = argparse.ArgumentParser(description="regulations.gov 출입처 의견서 감시(기자 전용 저장소로)")
    ap.parse_args()
    now = dt.datetime.now(KST)
    key = os.environ.get("REGULATIONS_GOV_API_KEY", "").strip() or "DEMO_KEY"
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    import private_store
    previous = None
    if token:
        try:
            previous = private_store.get("us-comments", token)
        except private_store.StoreError as e:
            print(f"::warning title=us-comments-state::이전 상태 조회 실패({e}) — 신규 표시는 이번 실행 기준")
    if private_store.late_scheduled_duplicate(previous, now):
        return
    doc = collect(key, now=now, previous=previous)
    ok = sum(1 for c in doc["checks"] if c["status"] == "ok")
    new = sum(1 for x in doc["items"] if x["isNew"])
    print(f"::notice title=us-comments::질의 정상 {ok}/{len(doc['checks'])} · 출입처 의견서 {len(doc['items'])}건(신규 {new}) · 키 {doc['keyType']}")
    if not token:
        print("::warning title=us-comments-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음(공개 저장소에도 쓰지 않음)")
        return
    if ok == 0:
        sys.exit("모든 질의 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("us-comments", doc, token)
    print(f"::notice title=us-comments-push::기자 전용 저장소 전송 HTTP {status}")
    if status == 404:
        print(f"::warning title=us-comments-push-token::토큰 거부 가능성 — {private_store.token_shape(private_store.normalize_token(token))}. GitHub Secret MCP_ACCESS_TOKEN이 Cloudflare 값과 같아야 함")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
