"""probe 213: 무역위 보도자료 PDF '(신청인)' 표 원문 구간(대리인·불공정 사건 꼴). 공개 자료. 저장 안 함. 요청 사이 1초."""
import re
import sys
import time

sys.path.insert(0, "scripts")
import requests  # noqa: E402
import ktc_watch as k  # noqa: E402

OUT = []
http = k.Http(requests.Session())
http.post(k.NEWS[0], {"menuId": k.NEWS[1]})
for bid in ("00002147", "00002167", "00002128", "00002109"):
    data, err = k.attachment_pdf(http, bid, time.sleep)
    text, err2 = k.pdf_text(data) if data else (None, err)
    t = re.sub(r"\s+", " ", text or "")
    OUT.append(f"P {bid} {err or err2 or ''} len {len(t)}")
    for m in re.finditer(r"\(\s*신청인\s*\)", t):
        OUT.append("   row: " + t[max(0, m.start() - 140):m.end() + 160])
    OUT.append("   parsed: " + repr(k.applicants_in(t)))
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
