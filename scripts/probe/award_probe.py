"""probe 199: 광양 새올 목록 HTTP 400(11-05·11-07 kr-local)이 GitHub에서 왜 나는지 — subCheck Y/N·쪽별. 천안 응답 시간도. 저장 안 함."""
import time
import requests

OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


PATH = "/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
LIST = {"method": "selectListOfrNotAncmt", "methodnm": "selectListOfrNotAncmtHomepage", "homepage_pbs_yn": "Y", "subCheck": "Y",
        "ofr_pageSize": "30", "not_ancmt_se_code": "01,02,03,04,05", "initValue": "Y", "countYn": "Y", "list_gubun": "A",
        "jndinm": "OfrNotAncmtEJB", "context": "NTIS", "method_type": ""}
for base, tries in (("https://eminwon.gwangyang.go.kr", [("Y", 1), ("Y", 2), ("N", 1), ("N", 2)]), ("https://eminwon.cheonan.go.kr", [("Y", 1)])):
    for sub, page in tries:
        t = time.time()
        try:
            r = requests.post(base + PATH, data={**LIST, "subCheck": sub, "pageIndex": str(page)}, headers={**UA, "Referer": base + PATH}, timeout=75)
            body = r.text
            log(base[8:26], f"sub={sub} p{page}", "HTTP", r.status_code, len(body), f"{time.time() - t:.1f}s", "rows", body.count("searchDetail("),
                "| " + (body[:160].replace("\n", " ") if r.status_code != 200 else ""))
        except Exception as e:  # noqa: BLE001
            log(base[8:26], f"sub={sub} p{page}", type(e).__name__, str(e)[:80], f"{time.time() - t:.1f}s")
        time.sleep(2)
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
