"""probe 193: 개인정보위 위원회 결정문 목록(agenda.do) — 처분 의결 제목 꼴·검색 인자·GS리테일 결정문 본문 꼴, GS리테일 대표이사 변경 공시.
공개 자료. 저장 안 함."""
import html, json, os, re, sys, time
import requests

sys.path.insert(0, "scripts")
OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


def clean(x):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x or ""))).strip()


s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 (compatible; ReporterRadar/1.0; public records)"})
t0 = time.time()
BASE = "https://www.pipc.go.kr/np/default/agenda.do"


def page(n, **kw):
    r = s.get(BASE, params={"mCode": "E030010000", "page": n, **kw}, timeout=30)
    rows = []
    for tr in re.findall(r"<tr\b.*?</tr>", r.text, re.S | re.I):
        tds = re.findall(r"<td\b[^>]*>(.*?)</td>", tr, re.S | re.I)
        idx = re.search(r"idxId=([\d-]+)", tr)
        if len(tds) >= 4 and idx:
            rows.append({"no": clean(tds[0]), "kind": clean(tds[1]), "title": clean(tds[2]), "date": clean(tds[3]), "idx": idx.group(1)})
    return r, rows


r, rows = page(1)
log(f"1쪽 HTTP {r.status_code} 줄 {len(rows)} · 마지막 쪽 링크 {re.findall(r'page=(\d+)[^>]*>\s*(?:<[^>]+>\s*)*(?:마지막|끝|last)', r.text, re.I)[:2]}")
for kw in ({"schStr": "지에스리테일"}, {"schStr": "GS리테일"}, {"schStr": "리테일", "schFld": "title"}):
    r2, rr = page(1, **kw)
    log(f"검색 {kw}: 줄 {len(rr)} · 첫 줄 {rr[0]['date'] + ' ' + rr[0]['title'][:60] if rr else None}")
    time.sleep(0.5)
sanction = re.compile(r"시정조치|과징금|과태료|처분|제재|법규\s*위반")
hits, kinds, pages_read = [], {}, 0
for n in range(1, 41):
    _, rr = page(n)
    pages_read += 1
    for x in rr:
        kinds[x["kind"]] = kinds.get(x["kind"], 0) + 1
        if sanction.search(x["title"]):
            hits.append(x)
    if rr and rr[-1]["date"] < "2026-07-01":
        break
    time.sleep(0.4)
log(f"읽은 쪽 {pages_read} · 회의구분 {kinds} · 처분 낱말 제목 {len(hits)}")
for x in hits[:25]:
    log(f"  {x['date']} {x['kind']} {x['idx']} {x['title'][:90]}")
gs = [x for x in hits if re.search(r"지에스리테일|GS\s*리테일|지에스", x["title"])]
log(f"GS 제목 {len(gs)}")
for x in (gs or hits)[:2]:
    r3 = s.get(BASE, params={"op": "view", "mCode": "E030010000", "idxId": x["idx"]}, timeout=30)
    t = clean(r3.text)
    log(f"[본문 {x['idx']}] HTTP {r3.status_code} 길이 {len(t)} · 첨부 {re.findall(r'(?:fileDown|FileDown|atchFileId)[^\"\\s]{0,80}', r3.text)[:3]}")
    for w in ("피 심 인", "피심인", "대표자", "대 표 자", "기간", "과징금", "주 문", "주문"):
        i = t.find(w)
        if i >= 0:
            log(f"   {w}: {t[max(0, i - 40):i + 160]}")
    time.sleep(0.5)
# GS리테일 대표이사 변경 공시(공개 공시)
key = os.environ.get("DART_API_KEY", "")
try:
    import dart_watch
    table = dart_watch.load_corp_codes(key)
    v = (table or {}).get("GS리테일") or (table or {}).get("지에스리테일") or []
    v = sorted(v, key=lambda x: not (x[1] or "").strip())
    code = v[0][0] if v else None
except Exception as e:
    code = None
    log("corp table", type(e).__name__)
log(f"GS리테일 고유번호 {code}")
if code:
    for ty in ("I", "B"):
        r4 = s.get("https://opendart.fss.or.kr/api/list.json", params={"crtfc_key": key, "corp_code": code, "bgn_de": "20241120", "end_de": "20250410",
                                                                       "pblntf_ty": ty, "page_count": 100}, timeout=30)
        for x in r4.json().get("list") or []:
            if re.search(r"대표이사|대표자", x["report_nm"]):
                log(f"  {ty} {x['rcept_dt']} {x['rcept_no']} {x['report_nm']}")
        time.sleep(0.4)
log(f"\n{time.time() - t0:.0f}s")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
