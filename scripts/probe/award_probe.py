"""probe 187: (a) 금감원 공개안 중 위반 기간을 못 뽑은 건(2020-07-08 우리은행 등)의 제재대상사실 날짜 표기, (b) 공정위 의결서 목록에서
사건번호로 원문(개방문서) 찾기 — searchKrwd 회사명 + 쪽 넘김, 원문 주문·과징금 발췌. 저장 안 함. 공개 처분 기록(법인)."""
import re, sys, time
import requests

sys.path.insert(0, "scripts")
import official_sanctions as osn  # noqa: E402
import kr_signals_watch as ks  # noqa: E402

OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


s = requests.Session()
s.headers.update(osn.UA)
t0 = time.time()
log("# 금감원 위반 기간 표기")
for rid in ("fss:201800707-2", "fss:201800707-1", "fss:201800707-3"):
    try:
        r = s.get(osn.fss_url(rid), timeout=30)
        hrefs = re.findall(r'href="([^"]*hpdownload[^"]*\.pdf[^"]*)"', r.text)
        if not hrefs:
            log(rid, "no pdf")
            continue
        p = s.get(requests.compat.urljoin("https://www.fss.or.kr/", hrefs[0].replace("&amp;", "&")), timeout=40)
        t = osn.pdf_text(p.content, 6)
        flat = re.sub(r"\s+", " ", t)
        k = flat.find("제재대상사실")
        log(f"\n {rid} chars {len(flat)} summary {({x: osn.fss_summary(t).get(x) for x in ('inst', 'exec', 'violation')})}")
        tail = flat[k:k + 5000]
        dates = re.findall(r"[^\s]{0,6}(?:(?:19|20)\d{2}|['’]\d{2})\s*[.년]\s*\d{1,2}[^\s]{0,12}", tail)
        log("  date tokens:", dates[:25])
        for m in re.finditer(r"기간\s*중|부터|까지|∼|~", tail):
            log("  ctx:", tail[max(0, m.start() - 50):m.end() + 20])
            if m.start() > 3000:
                break
    except Exception as e:
        log(rid, "error", type(e).__name__, str(e)[:100])
    time.sleep(0.5)

log("\n# 공정위 사건번호 → 원문")
for org, csno in (("지에스리테일", "2020서경1005"), ("엘지전자", "2019기감1114"), ("롯데지주", "2017건하2612")):
    try:
        found = None
        for page in range(1, 6):
            r = s.get(ks.FTC_LIST, params={"startRceptDt": "2016-01-01", "endRceptDt": "2026-11-05", "pageIndex": page, "searchKrwd": org}, timeout=40)
            rows, last = ks.parse_ftc_list(r.text)
            hit = next((x for x in rows if x["csno"] == csno), None)
            if hit:
                found = (page, hit)
                break
            if not rows or (last and page >= last):
                break
            time.sleep(0.5)
        if not found:
            log(f"\n {org} {csno}: 5쪽 안에 없음 (last {last})")
            continue
        page, hit = found
        log(f"\n {org} {csno}: page {page} name {hit['name'][:80]} action {hit['action']} doc {bool(hit.get('doc'))}")
        if hit.get("doc"):
            d = s.get(ks.FTC_TEXT, params={"docId": hit["doc"]["docId"], "docCnvrMnNo": hit["doc"]["docCnvrMnNo"]}, timeout=60)
            text = ks.doc_text(d.text)
            resp, order = ks.sections(text)
            amounts = re.findall(r"([\d,]{4,})\s*(백만원|천원|원)", order)
            log("  resp:", resp[:200])
            log("  order:", order[:400])
            log("  amounts:", amounts[:5])
    except Exception as e:
        log(org, "error", type(e).__name__, str(e)[:100])
    time.sleep(0.5)
log(f"\n{time.time() - t0:.0f}s")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
