"""probe 254: USTR 원천 — regulations.gov의 USTR 도켓·의견서(한국·출입처 낱말), 연방관보 USTR 고시, comments.ustr.gov, ustr.gov 보도자료.
공개 정부 자료만. 저장 안 함."""
import collections
import datetime as dt
import os
import re
import time

import requests

OUT = []
UA = {"User-Agent": "Mozilla/5.0 (seoul-reporting-radar probe)", "Accept": "application/json"}
KEY = os.environ.get("REGULATIONS_GOV_API_KEY", "").strip() or "DEMO_KEY"
API = "https://api.regulations.gov/v4"
now = dt.datetime.utcnow()
d = lambda n: (now - dt.timedelta(days=n)).strftime("%Y-%m-%d")
calls = [0]


def reg(path, params):
    calls[0] += 1
    try:
        r = requests.get(API + path, params={**params, "api_key": KEY}, headers=UA, timeout=40)
        time.sleep(1.3)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        return r.json(), None
    except Exception as e:  # noqa: BLE001
        return None, type(e).__name__


def part_a():
    OUT.append(f"[가] regulations.gov 키 {'있음' if KEY != 'DEMO_KEY' else '없음(DEMO_KEY)'}")
    body, err = reg("/dockets", {"filter[agencyId]": "USTR", "sort": "-lastModifiedDate", "page[size]": "30"})
    if err:
        OUT.append(f"   USTR 도켓 목록 실패 {err}")
    else:
        rows = body.get("data") or []
        OUT.append(f"   USTR 도켓 전체 {(body.get('meta') or {}).get('totalElements')}개 · 최근 고친 것 {len(rows)}개:")
        for x in rows[:22]:
            a = x.get("attributes") or {}
            OUT.append(f"   · {x.get('id')} | {str(a.get('lastModifiedDate'))[:10]} | {str(a.get('title'))[:120]}")
    # 최근 60일 USTR 의견서: 도켓별 건수
    cnt, total, page = collections.Counter(), None, 1
    while page <= 4:
        body, err = reg("/comments", {"filter[agencyId]": "USTR", "filter[postedDate][ge]": d(60), "sort": "-postedDate", "page[size]": "250", "page[number]": str(page)})
        if err:
            OUT.append(f"   최근 60일 의견서 실패 {err}")
            break
        total = (body.get("meta") or {}).get("totalElements")
        rows = body.get("data") or []
        for x in rows:
            cid = x.get("id") or ""
            cnt[cid.rsplit("-", 1)[0]] += 1
        if not (body.get("meta") or {}).get("hasNextPage"):
            break
        page += 1
    OUT.append(f"   최근 60일 USTR 의견서 {total}건 · 읽은 {sum(cnt.values())}건의 도켓별: {cnt.most_common(8)}")
    # 낱말 검색(최근 120일, USTR)
    for term in ['"Korea"', '"Korean"', '"Hyundai"', '"POSCO"', '"Hanwha"', '"LG Chem"', '"Lotte Chemical"', '"Korea Zinc"', '"HD Hyundai"', '"LS Electric"', '"SK Innovation"', '"Kumho"', '"Hankook"', '"SeAH"']:
        body, err = reg("/comments", {"filter[agencyId]": "USTR", "filter[searchTerm]": term, "filter[postedDate][ge]": d(120), "sort": "-postedDate", "page[size]": "25"})
        if err:
            OUT.append(f"   {term}: 실패 {err}")
            continue
        rows = body.get("data") or []
        tot = (body.get("meta") or {}).get("totalElements")
        dk = collections.Counter((x.get("id") or "").rsplit("-", 1)[0] for x in rows)
        OUT.append(f"   {term} 최근 120일 {tot}건 · 도켓 {dk.most_common(4)}")
        show = 8 if term in ('"Korea"', '"Hyundai"') else 3
        for x in rows[:show]:
            a = x.get("attributes") or {}
            OUT.append(f"      - {str(a.get('postedDate'))[:10]} | {x.get('id')} | {str(a.get('title'))[:110]}")
    OUT.append(f"   호출 {calls[0]}번")


def part_b():
    try:
        r = requests.get("https://www.federalregister.gov/api/v1/documents.json", params={"conditions[agencies][]": "trade-representative-office-of-united-states",
                         "conditions[publication_date][gte]": d(90), "order": "newest", "per_page": "60", "fields[]": ["title", "publication_date", "document_number", "docket_ids", "type", "abstract"]}, headers=UA, timeout=40)
        rows = r.json().get("results") or []
        kr = [x for x in rows if re.search(r"Korea", f"{x.get('title')} {x.get('abstract')}", re.I)]
        OUT.append(f"[나] 연방관보 USTR 고시 최근 90일 {r.json().get('count')}건 · 한국 낱말 {len(kr)}건")
        for x in rows[:16]:
            OUT.append(f"   · {x.get('publication_date')} | {x.get('document_number')} | {(x.get('docket_ids') or [''])[0]} | {str(x.get('title'))[:120]}")
        r = requests.get("https://www.federalregister.gov/api/v1/public-inspection-documents/current.json", headers=UA, timeout=40)
        pi = [x for x in (r.json().get("results") or []) if any("trade-representative" in str(a.get("slug")) for a in (x.get("agencies") or []))]
        OUT.append(f"   사전 공개본 중 USTR {len(pi)}건: " + " / ".join(str(x.get("toc_doc") or x.get("title"))[:80] for x in pi[:4]))
    except Exception as e:  # noqa: BLE001
        OUT.append(f"[나] 연방관보 실패 {type(e).__name__}: {str(e)[:120]}")


def page(name, url, pats=()):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"}, timeout=40)
        b = r.text
        t = re.search(r"<title[^>]*>(.*?)</title>", b, re.S | re.I)
        plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)\b.*?</\1>", " ", b, flags=re.S | re.I)))
        OUT.append(f"[{name}] HTTP {r.status_code} · {len(b)}자 · 제목 {re.sub(chr(10), ' ', t.group(1)).strip()[:70] if t else '?'} · 스크립트 {len(re.findall(r'<script', b, re.I))}개")
        for p in pats:
            hits = list(re.finditer(p, plain, re.I))
            OUT.append(f"   '{p}' {len(hits)}곳" + "".join(f" | {plain[max(0, m.start() - 70):m.end() + 110].strip()[:190]}" for m in hits[:3]))
        return b
    except Exception as e:  # noqa: BLE001
        OUT.append(f"[{name}] 실패 {type(e).__name__}: {str(e)[:120]}")
        return ""


def part_c():
    page("comments.ustr.gov", "https://comments.ustr.gov/s/", [r"docket", r"Korea"])
    b = page("ustr.gov 보도자료", "https://ustr.gov/about-us/policy-offices/press-office/press-releases", [r"Korea", r"Section 301", r"November \d+, 2026|October \d+, 2026"])
    links = re.findall(r'href="(/about[^"]*press-releases/2026/[^"]+)"[^>]*>([^<]{10,160})<', b)
    OUT.append(f"   2026 보도자료 링크 {len(links)}개: " + " / ".join(t.strip()[:70] for _, t in links[:8]))
    page("ustr.gov 한국 페이지", "https://ustr.gov/countries-regions/japan-korea-apec/korea", [r"2026", r"Joint Fact Sheet|agreement|tariff"])
    page("ustr.gov FOIA 열람실", "https://ustr.gov/about-us/reading-room/freedom-information-act-foia/electronic-reading-room", [r"Korea", r"2026"])


for f in (part_a, part_b, part_c):
    try:
        f()
    except Exception as e:  # noqa: BLE001
        OUT.append(f"[{f.__name__}] 예외 {type(e).__name__}: {str(e)[:200]}")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
