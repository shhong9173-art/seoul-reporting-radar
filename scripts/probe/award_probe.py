"""probe 215: 새 첨부 읽기(hwpx·hwp·PDF 20쪽)와 옛 '신청인 :' 꼴을 실제 보도자료에 돌려 본다. 공개 자료. 저장 안 함. 요청 사이 1초. 한 번만."""
import re
import sys
import time

sys.path.insert(0, "scripts")
import requests  # noqa: E402
import ktc_watch as k  # noqa: E402

OUT = []
http = k.Http(requests.Session())
http.post(k.NEWS[0], {"menuId": k.NEWS[1]})
IDS = ["00001891", "00001776", "00001771", "00001768", "00001723", "00001722", "00001713", "00001701", "00001690", "00001689", "00001669", "00001668",
       "00001662", "00001654", "00002297", "00002167", "00002147", "00002128"]
for bid in IDS:
    text, err, kind = k.attachment_text(http, bid, time.sleep)
    t = re.sub(r"\s+", " ", text or "")
    odd = len(re.findall(r"[一-鿿]", t))
    got = k.applicants_in(t)
    OUT.append(f"P {bid} {kind} len {len(t)} 한자 {odd} {err or ''}")
    for a in got:
        OUT.append(f"   {a['how']} | {a['product']} | {', '.join(a['names'])} | 출입처 {','.join(a['beat']) or '-'}")
    n_app = len(re.findall(r"신청인", t))
    if not got and n_app:
        for m in list(re.finditer(r"(?<![가-힣])신청인", t))[:2]:
            OUT.append("   ctx: " + t[max(0, m.start() - 80):m.end() + 100])
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
