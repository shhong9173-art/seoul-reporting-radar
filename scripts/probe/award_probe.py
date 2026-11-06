"""probe 197: 개인정보위 결정문 — pipc_decision이 못 읽은(parsed_empty) 첨부의 첫머리 꼴. 공개 자료. 저장 안 함."""
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
rows = []
for n in range(1, 7):
    r = s.get(osn.PIPC_AGENDA, params={"mCode": "E030010000", "page": n}, timeout=30)
    rows += [x for x in osn.pipc_agenda_rows(r.text) if osn.PIPC_DECISION_TITLE.search(x["title"]) and "공공기관" not in x["title"]]
    time.sleep(0.4)
log(f"처분 제목 {len(rows)}")
empty = ok = 0
for x in rows[:22]:
    v = s.get(osn.PIPC_AGENDA_VIEW + x["idx"], timeout=30)
    files = list(dict.fromkeys(re.findall(r"fn_egov_downFileCnv\(\s*'([^']+)'\s*,\s*'(\d+)'\s*,\s*'pdf'", v.text)))
    for fid, sn in files[:1]:
        f = s.get(osn.PIPC_FILE_DL, params={"atchFileId": fid, "fileSn": sn, "fileExtsn": "pdf", "cnvCnt": "1"}, headers={"Referer": v.url}, timeout=60)
        if f.content[:4] != b"%PDF":
            log(f"[{x['idx']}] PDF 아님")
            continue
        t = osn.pdf_text(f.content, 40)
        d = osn.pipc_decision(t)
        tt = re.sub(r"\s+", " ", t)
        if d:
            ok += 1
            log(f"[{x['idx']} {x['kind']}] ok {[(y['org'][:10], y['date'], y.get('fine'), y.get('penalty')) for y in d][:4]} · 안건번호 수 {len(re.findall(r'안\s*건\s*번\s*호', tt))}")
        else:
            empty += 1
            log(f"[{x['idx']} {x['kind']} 파일 {len(files)}] 빈 · 글자 {len(tt)} · 첫머리 {tt[:420]}")
            for w in ("피심인", "피 심 인", "의결", "의 결", "주 문", "주문", "과태료", "과 태 료"):
                i = tt.find(w)
                if i >= 0:
                    log(f"   {w}: …{tt[max(0, i - 30):i + 120]}…")
        time.sleep(0.6)
    time.sleep(0.4)
log(f"ok {ok} · 빈 {empty} · {time.time() - t0:.0f}s")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
