"""probe 185: 금감원 제재내용공개 상세(예전 건) — 공개안 PDF 링크 형식과 fss_detail 결과. 저장 안 함. 공개안엔 개인 이름이 없다."""
import re, sys, time
import requests

sys.path.insert(0, "scripts")
import official_sanctions as osn  # noqa: E402

OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


s = requests.Session()
s.headers.update(osn.UA)
t0 = time.time()
for rid in ("fss:201800707-4", "fss:202000209-1", "fss:201900890-2", "fss:202200225-1", "fss:202400672-1"):
    url = osn.fss_url(rid)
    try:
        r = s.get(url, timeout=30)
        hrefs = re.findall(r'href="([^"]*hpdownload[^"]*)"', r.text)
        log(f"\n# {rid} HTTP {r.status_code} {len(r.text)}B hpdownload {len(hrefs)}")
        for h in hrefs[:4]:
            log("   ", h[:200])
        other = re.findall(r'href="([^"]+\.(?:pdf|hwp|hwpx|zip)[^"]*)"', r.text, re.I)
        log("  other file hrefs", [x[:160] for x in other[:4]])
        d = osn.fss_detail({"id": rid, "url": url}, get=s.get)
        log("  fss_detail:", {k: (v[:120] if isinstance(v, str) else v) for k, v in d.items()})
        if hrefs:
            p = s.get(requests.compat.urljoin("https://www.fss.or.kr/", hrefs[0].replace("&amp;", "&")), timeout=40)
            log("  file", p.status_code, p.headers.get("Content-Type", "")[:40], len(p.content), p.content[:6])
            if p.content[:4] == b"%PDF":
                t = osn.pdf_text(p.content, 2)
                log("  text head:", re.sub(r"\s+", " ", t)[:700])
    except Exception as e:
        log("  error", type(e).__name__, str(e)[:120])
    time.sleep(0.5)
log(f"\n{time.time() - t0:.0f}s")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
