"""USTR 의견서 속 한국·출입 업종(regulations.gov): 다른 단체·기업이 USTR에 낸 의견서 첨부 본문에서 한국을 지목한 대목.

왜: 11-15 기자 "선배가 USTR에서도 단독 나온다는데". 확인해 보니 최근 2주 타사 단독 3건이 USTR 의견서였다(11-13 TV조선 CTA,
11-05 신아일보 미 반도체업계, 11-02 더투데이 301조 삼성·테슬라). 레이더의 '미 연방 의견서'(us_comments_watch)는 출입처가
직접 낸 의견서만 보고 "다른 단체 의견서가 출입처를 인용한 것은 제외"하고 있었다 — 그 빠진 쪽이다.

읽는 것:
  · regulations.gov의 USTR 의견서 전부(최근 45일 게시분, 도켓 가리지 않음) — 국가별 무역장벽보고서(NTE, 해마다 10월 말),
    스페셜 301(1~2월), 301조 조사, 협정 운영 의견 등. 한 번 읽은 의견서는 다시 받지 않는다.
  · 첨부 PDF 본문(의견서 하나에 3개·90쪽까지)에서 한국 낱말(Korea·KORUS·ROK, North Korea 제외)을 찾고,
    그 앞뒤에 출입 업종 낱말(자동차·철강·비철·화학·정유·전력기기·에너지)이나 출입처 영문 이름이 있는 대목만 남긴다.
    regulations.gov 낱말 검색은 첨부 본문을 다 찾지 못한다(probe 254: NTE 186건 중 "Korea" 10건) — 그래서 첨부를 직접 읽는다.
  · 연방관보의 USTR 고시(최근 45일)와 의견 마감일 — 다음 의견서가 언제 쏟아지는지.

한계(화면에도 적는다): 의견서는 낸 쪽의 주장이고 USTR 판단이 아니다. 스캔본 PDF는 글자를 못 뽑는다(건수로 남김).
301조 의견이 들어가는 USTR 자체 포털(comments.ustr.gov)은 읽지 못한다 — 미확인. 발췌는 영어 원문 그대로다.
결과는 기자 전용 저장소(ustr-comments)로만. 공개 로그에는 건수만.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import us_comments_watch as uc  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "ustr_comments/v1"
LOOKBACK_DAYS = 45
READ_BUDGET = 130     # 한 실행에 본문까지 읽는 의견서 수 — 넘으면 '대기'(0건 아님), 다음 실행에서 읽는다
KEEP_DAYS = 200       # 잡힌 의견서를 화면에 두는 기간
FILE_MAX = 25_000_000
PAGES = 90
FILES = 3
BASELINE_DAYS = 3     # 감시를 시작한 날보다 이만큼 넘게 먼저 게시된 것은 기준선(새 항목으로 올리지 않는다 — 화면에는 보인다)
UA = "Mozilla/5.0 (seoul-reporting-radar)"
# 첨부 내려받기(downloads.regulations.gov)는 위 UA에 HTTP 403을 준다(11-15 첫 운영 실행: 302건 중 239건을 못 받고 '스캔본'으로 잘못 셌다 — probe 257).
# 같은 이름을 밝힌 다른 꼴의 UA는 받는다. 403이면 다음 꼴로 한 번 더 받는다. 브라우저인 척하지 않는다.
DOWNLOAD_UAS = ("Mozilla/5.0 (compatible; seoul-reporting-radar/1.0; newsroom research)", "Mozilla/5.0 (seoul-reporting-radar probe)")
VERSION = 2           # 읽기 방식이 바뀌면 올린다 — 앞서 읽은 목록을 버리고 한 번 다시 읽는다
FR_API = "https://www.federalregister.gov/api/v1/documents.json"

KOREA = re.compile(r"(?<![Nn]orth )\bKorea(?:n|ns|'s|’s)?\b|\bKORUS\b|\bROK\b")
SECTORS = {
    "자동차": re.compile(r"automo|motor vehicle|\bvehicles?\b|\bcars?\b|\bEVs?\b|fuel econom|\btires?\b|light trucks?", re.I),
    "철강·비철": re.compile(r"\bsteel|\biron\b|alumin|\bzinc\b|\bcopper\b|critical minerals?", re.I),
    "화학·정유": re.compile(r"chemical|petrochem|refiner|refined|epoxy|\bresins?\b|polymer|ethylene|K-REACH|lubricant|ethanol|biofuel|\brubber\b", re.I),
    "전력기기·에너지": re.compile(r"transformer|electrical equipment|\bcables?\b|\bsolar\b|batter|hydrogen|\bnuclear\b|\bLNG\b|electricity (?:price|rate|tariff|subsid)|power grid", re.I),
}
# 출입처 영문 이름(us_comments_watch와 같은 목록) — 계열사 꼬리(International·Future M·Energy Solution)는 출입처가 아니다
NOT_BEAT = re.compile(r"\s+(?:International|Future\s*M|Energy Solution|On\b|Engineering|E&C|Heavy Industries)", re.I)


def companies_in(text):
    out = []
    for label, _, pattern in uc.COMPANIES:
        for m in re.finditer(pattern, text, re.I):
            if NOT_BEAT.match(text[m.end():m.end() + 24]):
                continue
            name = re.sub(r"^제네시스\((.+)\)$", r"\1", label)
            for part in name.split("·"):
                if part not in out:
                    out.append(part)
            break
    return out


def analyze(text):
    """본문 → {'korea': 한국 낱말 수, 'hits': [{'sectors', 'companies', 'excerpt'}]} — 업종 낱말이나 출입처 이름이 곁에 있는 대목만."""
    spots = [m for m in KOREA.finditer(text)]
    hits, last_end = [], -1
    for m in spots:
        if m.start() < last_end:
            continue   # 앞 대목과 겹치는 한국 낱말
        a, b = max(0, m.start() - 380), min(len(text), m.end() + 520)
        ctx = re.sub(r"\s+", " ", text[a:b]).strip()
        sectors = [k for k, rx in SECTORS.items() if rx.search(ctx)]
        names = companies_in(ctx)
        if sectors or names:
            hits.append({"sectors": sectors, "companies": names, "excerpt": ctx})
            last_end = b
    hits.sort(key=lambda h: (-len(h["companies"]), -len(h["sectors"])))
    return {"korea": len(spots), "hits": hits}


def pdf_text(data):
    import pypdf
    pdf = pypdf.PdfReader(io.BytesIO(data))
    out = []
    for i, page in enumerate(pdf.pages):
        if i >= PAGES:
            break
        try:
            out.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001
            out.append("")
    return re.sub(r"[ \t]+", " ", "\n".join(out)), len(pdf.pages)


def download(url, get, sleep):
    """첨부 한 개 → (바이트 또는 None, 오류). 403이면 다른 꼴의 UA로 한 번 더."""
    err = None
    for ua in DOWNLOAD_UAS:
        try:
            r = get(url, headers={"User-Agent": ua}, timeout=60)
        except Exception as e:  # noqa: BLE001
            err = type(e).__name__
            continue
        finally:
            sleep(0.4)
        if r.status_code == 200 and r.content[:5] == b"%PDF-":
            return (r.content if len(r.content) <= FILE_MAX else None), (None if len(r.content) <= FILE_MAX else "첨부가 너무 큼")
        err = f"첨부 HTTP {r.status_code}" if r.status_code != 200 else "첨부가 PDF가 아님"
        if r.status_code != 403:
            break
    return None, err


def read_comment(cid, key, *, get, sleep, budget):
    """의견서 하나의 글자(입력 칸 + 첨부 PDF) → (상태, 글자, 쪽수, 첨부 수, 오류).
    상태: ok / nopdf(첨부 없음) / scan(받았는데 글자를 못 뽑음) / failed(상세 조회나 첨부 내려받기 실패 — 다음 실행에서 다시)"""
    status, body = uc.call(f"/comments/{cid}", {"include": "attachments"}, key, get=get, budget=budget, sleep=sleep)
    if status != "ok":
        return "failed", "", 0, 0, str(body or status)
    text = str(((body.get("data") or {}).get("attributes") or {}).get("comment") or "")
    urls = []
    for inc in body.get("included") or []:
        for f in (inc.get("attributes") or {}).get("fileFormats") or []:
            if str(f.get("format")).lower() == "pdf" and f.get("fileUrl"):
                urls.append(f["fileUrl"])
    pages, got, fetched, err = 0, 0, 0, None
    for url in urls[:FILES]:
        data, e = download(url, get, sleep)
        if data is None:
            err = e or err
            continue
        fetched += 1
        try:
            t, n = pdf_text(data)
        except Exception as ex:  # noqa: BLE001
            err = f"PDF 읽기 {type(ex).__name__}"
            continue
        text += "\n" + t
        pages += n
        got += 1 if len(t) > 300 else 0
    if not urls:
        return ("ok" if len(text) > 200 else "nopdf"), text, 0, 0, None
    if not fetched:
        return "failed", text, 0, len(urls), err or "첨부 내려받기 실패"
    if not got:
        return "scan", text, pages, len(urls), err
    return "ok", text, pages, len(urls), None


def notices(now, get):
    """연방관보의 USTR 고시(최근 45일): 제목·게재일·도켓·의견 마감일."""
    try:
        r = get(FR_API, params={"conditions[agencies][]": "trade-representative-office-of-united-states",
                                "conditions[publication_date][gte]": (now - dt.timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d"),
                                "order": "newest", "per_page": "40",
                                "fields[]": ["title", "publication_date", "document_number", "docket_ids", "comments_close_on", "html_url", "abstract"]},
                headers={"User-Agent": UA}, timeout=40)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        out = []
        for x in r.json().get("results") or []:
            blob = f"{x.get('title')} {x.get('abstract')}"
            out.append({"date": x.get("publication_date"), "number": x.get("document_number"), "title": str(x.get("title") or "")[:240],
                        "docket": (x.get("docket_ids") or [None])[0], "closes": x.get("comments_close_on"), "url": x.get("html_url"),
                        "korea": bool(KOREA.search(blob)), "sectors": [k for k, rx in SECTORS.items() if rx.search(blob)]})
        return out, None
    except Exception as e:  # noqa: BLE001
        return None, type(e).__name__


def collect(key, *, now, previous=None, get=None, sleep=time.sleep, budget=None, read_budget=READ_BUDGET):
    if get is None:
        import requests
        get = requests.get
    budget = budget or uc.Budget(int(os.environ.get("REGS_CALL_BUDGET", "40" if key == "DEMO_KEY" else "320")))
    prev = previous if isinstance(previous, dict) else {}
    started = str(prev.get("startedAt") or now.isoformat(timespec="seconds"))
    same = prev.get("v") == VERSION
    seen = dict(prev.get("seen") or {}) if same else {}   # 읽기 방식이 바뀌었으면 처음부터 다시 읽는다(감시 시작일은 지킨다)
    dockets = dict(prev.get("docketTitles") or {})
    since = (now - dt.timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    stamp = now.isoformat(timespec="seconds")
    checks, listed, page = [], [], 1
    while page <= 6:
        status, body = uc.call("/comments", {"filter[agencyId]": "USTR", "filter[postedDate][ge]": since, "sort": "-postedDate",
                                             "page[size]": 250, "page[number]": page}, key, get=get, budget=budget, sleep=sleep)
        if status != "ok":
            checks.append({"source": f"USTR 의견서 목록 {page}쪽", "status": status, **({"error": body} if body else {})})
            break
        listed += body.get("data") or []
        checks.append({"source": f"USTR 의견서 목록 {page}쪽", "status": "ok", "returned": len(body.get("data") or [])})
        if not (body.get("meta") or {}).get("hasNextPage"):
            break
        page += 1
    items = {x["id"]: x for x in (prev.get("items") or []) if isinstance(x, dict) and x.get("id")} if same else {}
    # 기준선: 감시 시작일보다 사흘 넘게 먼저 게시된 의견서(첫 읽기가 여러 실행에 걸쳐도 같은 기준)
    cutoff = (dt.datetime.fromisoformat(started) - dt.timedelta(days=BASELINE_DAYS)).strftime("%Y-%m-%d")
    read = waiting = 0
    for d in listed:
        cid = d.get("id")
        a = d.get("attributes") or {}
        old = seen.get(cid)
        if old and old.get("status") in ("ok", "nopdf", "scan"):
            continue
        if old and old.get("tries", 0) >= 3:
            continue   # 세 번 실패한 의견서는 더 받지 않는다(실패로 남는다)
        if read >= read_budget:
            waiting += 1
            continue
        read += 1
        posted = str(a.get("postedDate") or "")[:10]
        status, text, pages, nfiles, err = read_comment(cid, key, get=get, sleep=sleep, budget=budget)
        found = analyze(text) if status == "ok" else {"korea": 0, "hits": []}
        seen[cid] = {"status": status, "posted": posted, "korea": found["korea"], "hits": len(found["hits"]), **({"tries": (old or {}).get("tries", 0) + 1, "error": err} if status == "failed" else {})}
        # 지나가며 한 번 적은 한국(나라 이름 나열 속 'Korea' + 업종 낱말 한 곳)은 항목으로 올리지 않는다 — 11-15 첫 운영: CBAM 도켓 의견서 5건 중 3건이 그런 것.
        # 출입처 이름이 있거나 한국·업종 대목이 두 곳 이상일 때만.
        if not found["hits"] or not (len(found["hits"]) >= 2 or any(h["companies"] for h in found["hits"])):
            continue
        did = cid.rsplit("-", 1)[0] if "-" in cid else None
        sectors = [k for k in SECTORS if any(k in h["sectors"] for h in found["hits"])]
        names = []
        for h in found["hits"]:
            names += [n for n in h["companies"] if n not in names]
        items[f"ustr:{cid}"] = {
            "id": f"ustr:{cid}", "commentId": cid, "tier": "B", "submitter": uc.submitter_of(a.get("title")) or str(a.get("title") or "")[:120],
            "docketId": did, "postedDate": posted, "url": f"https://www.regulations.gov/comment/{cid}", "korea": found["korea"], "pages": pages,
            "sectors": sectors, "companies": names, "excerpts": [h["excerpt"][:620] for h in found["hits"][:3]], "passages": len(found["hits"]),
            "firstSeen": stamp, "baseline": posted < cutoff,
        }
    # 도켓 제목(새 도켓만)
    for x in items.values():
        did = x.get("docketId")
        if did and did not in dockets:
            status, body = uc.call(f"/dockets/{did}", {}, key, get=get, budget=budget, sleep=sleep)
            if status == "ok":
                dockets[did] = re.sub(r"\s+", " ", ((body.get("data") or {}).get("attributes") or {}).get("title") or "")[:200]
        if did in dockets:
            x["docketTitle"] = dockets[did]
    keep = (now - dt.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    rows = sorted((x for x in items.values() if str(x.get("postedDate") or "9") >= keep), key=lambda x: (x.get("postedDate") or "", x["id"]), reverse=True)
    seen = {k: v for k, v in seen.items() if str(v.get("posted") or "9") >= keep}
    fr, fr_err = notices(now, get)
    checks.append({"source": "연방관보 USTR 고시", "status": "ok" if fr is not None else "failed", **({"returned": len(fr)} if fr is not None else {"error": fr_err})})
    if waiting:
        checks.append({"source": "본문 읽기 한도", "status": "waiting", "error": f"{waiting}건 다음 실행에서 읽음"})
    by = lambda s: sum(1 for v in seen.values() if v.get("status") == s)
    list_ok = any(c["source"].startswith("USTR 의견서 목록") and c["status"] == "ok" for c in checks)
    return {
        "schema": SCHEMA, "v": VERSION, "generatedAt": stamp, "startedAt": started, "status": "ok" if list_ok and not waiting and not by("failed") and fr is not None else "partial" if list_ok else "failed",
        "source": "regulations.gov API v4(USTR 의견서·첨부 PDF) · federalregister.gov API(USTR 고시)", "keyType": "DEMO_KEY" if key == "DEMO_KEY" else "개인 키",
        "lookbackDays": LOOKBACK_DAYS, "checks": checks, "items": rows, "seen": seen, "docketTitles": dockets, "notices": fr if fr is not None else (prev.get("notices") or []),
        "summary": {"listed": len(listed), "readNow": read, "waiting": waiting, "known": len(seen), "scan": by("scan"), "nopdf": by("nopdf"), "failed": by("failed"),
                    "korea": sum(1 for v in seen.values() if v.get("korea")), "items": len(rows), "fresh": sum(1 for x in rows if x.get("firstSeen") == stamp and not x.get("baseline"))},
        "rules": ["의견서는 낸 쪽의 주장이다 — USTR 판단이 아니고, 한국 정부·회사 입장은 따로 확인한다.",
                  "발췌는 영어 원문 그대로다. 기사에 쓸 때는 원문 PDF의 쪽·문단을 다시 확인한다.",
                  "USTR 자체 의견 포털(comments.ustr.gov — 301조 조사 의견)은 읽지 못한다. 스캔본 PDF는 글자를 못 뽑는다."],
    }


def main():
    ap = argparse.ArgumentParser(description="USTR 의견서 속 한국·출입 업종(기자 전용 저장소로)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--read", type=int, default=READ_BUDGET, help="이번 실행에 본문까지 읽을 의견서 수(첫 실행 때 한 번에 다 읽으려면 크게)")
    a = ap.parse_args()
    now = dt.datetime.now(KST)
    key = os.environ.get("REGULATIONS_GOV_API_KEY", "").strip() or "DEMO_KEY"
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    import private_store
    previous = None
    if token:
        try:
            previous = private_store.get("ustr-comments", token)
        except private_store.StoreError as e:
            print(f"::warning title=ustr-comments-state::이전 상태 조회 실패({e}) — 이번에는 저장하지 않는다(읽은 목록을 지우지 않으려고)")
            return 0
    read = 12 if a.dry_run else max(1, min(a.read, 600))
    doc = collect(key, now=now, previous=previous, read_budget=read, budget=uc.Budget(read * 2 + 40) if key != "DEMO_KEY" else None)
    s = doc["summary"]
    # 공개 로그에는 건수만(제출자·발췌는 찍지 않는다)
    print(f"::notice title=ustr-comments::목록 {s['listed']}건 · 이번에 본문 읽음 {s['readNow']} · 대기 {s['waiting']} · 누적 읽음 {s['known']}(스캔본 {s['scan']}·첨부 없음 {s['nopdf']}·실패 {s['failed']}) · "
          f"한국 언급 {s['korea']}건 · 출입 업종 대목 {s['items']}건(이번 새 항목 {s['fresh']}) · 관보 고시 {len(doc['notices'])}건 · 키 {doc['keyType']}")
    if a.dry_run or not token:
        return 0
    if doc["status"] == "failed":
        sys.exit("USTR 의견서 목록 조회 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("ustr-comments", doc, token)
    print(f"::notice title=ustr-comments-push::기자 전용 저장소 전송 HTTP {status}")
    return 0 if status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
