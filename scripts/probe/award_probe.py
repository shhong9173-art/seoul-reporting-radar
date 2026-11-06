"""probe 195: 개인정보위 위원회 결정문 첨부 내려받기 경로(JS 함수 본문) 찾기 + 시도. 공개 자료. 저장 안 함."""
import html, re, sys, time
import requests

sys.path.insert(0, "scripts")
import official_sanctions as osn  # noqa: E402

OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 (compatible; ReporterRadar/1.0; public records)"})
t0 = time.time()
BASE = "https://www.pipc.go.kr/np/default/agenda.do"
v = s.get(BASE, params={"op": "view", "mCode": "E030010000", "idxId": "2026-0723"}, timeout=30)
t = v.text
for m in re.finditer(r"function\s+\w+\s*\([^)]*atchFileId[^)]*\)\s*\{", t):
    log("FUNC " + re.sub(r"\s+", " ", t[m.start():m.start() + 900]))
for m in re.finditer(r"<form[^>]*>", t, re.I):
    log("FORM " + m.group(0)[:200])
for m in re.finditer(r"CYLFILE_000000020771", t):
    log("CTX " + re.sub(r"\s+", " ", t[max(0, m.start() - 300):m.start() + 120]))
    break
log("action 후보 " + str(sorted(set(re.findall(r"['\"](/[\w/]+\.do)['\"]", t)))[:20]))
ref = v.url
tries = [("GET", "https://www.pipc.go.kr/np/cmm/fms/FileDown.do", {"atchFileId": "CYLFILE_000000020771", "fileSn": "3"}),
         ("GET", "https://www.pipc.go.kr/np/cmm/fms/FileDown.do", {"atchFileId": "CYLFILE_000000020771", "fileSn": "3", "fileExt": "pdf"}),
         ("POST", "https://www.pipc.go.kr/np/cmm/fms/FileDown.do", {"atchFileId": "CYLFILE_000000020771", "fileSn": "3", "fileExt": "pdf"}),
         ("GET", "https://www.pipc.go.kr/np/default/agendaFileDown.do", {"atchFileId": "CYLFILE_000000020771", "fileSn": "3", "fileExt": "pdf"}),
         ("GET", "https://www.pipc.go.kr/np/cmm/fms/FileDownPdf.do", {"atchFileId": "CYLFILE_000000020771", "fileSn": "3"})]
for meth, url, data in tries:
    try:
        r = s.get(url, params=data, headers={"Referer": ref}, timeout=40) if meth == "GET" else s.post(url, data=data, headers={"Referer": ref}, timeout=40)
        txt = osn.attachment_text(r.content) if r.status_code == 200 else None
        log(f"{meth} {url.rsplit('/', 1)[-1]} {data.get('fileExt', '')} → HTTP {r.status_code} 머리 {r.content[:4]!r} 크기 {len(r.content)} 형식 {r.headers.get('Content-Type', '')[:40]} 글자 {len(txt or '')}")
        if txt:
            tt = re.sub(r"\s+", " ", txt)
            log("   첫머리 " + tt[:600])
            for w in ("피 심 인", "피심인", "대 표 자", "대표자", "위반기간", "과 징 금", "과징금"):
                i = tt.find(w)
                if i >= 0:
                    log(f"   {w}: …{tt[max(0, i - 20):i + 160]}…")
            break
    except Exception as e:
        log(meth, url, type(e).__name__)
    time.sleep(0.6)
log(f"\n{time.time() - t0:.0f}s")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
