"""probe 212: 무역위 보도자료 첨부(POST /boardFileDownload.do bbs_id·seq_no) — PDF 본문의 신청인 문구. 공개 자료. 저장 안 함. 요청 사이 1초."""
import re
import sys
import time

sys.path.insert(0, "scripts")
import requests  # noqa: E402
import ktc_watch as k  # noqa: E402

OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


http = k.Http(requests.Session())
http.post(k.NEWS[0], {"menuId": k.NEWS[1]})   # 세션
IDS = [("00002147", "부틸 아크릴레이트"), ("00002157", "수산화나트륨"), ("00002167", "H형강·봉강"), ("00002297", "아연도금냉연"),
       ("00002129", "동관"), ("00002128", "PVC 페이스트"), ("00002113", "아연 표면처리 냉연"), ("00002109", "산업용로봇")]
for bid, name in IDS:
    for seq in ("0000", "0001"):
        time.sleep(1)
        try:
            r = http.s.post(k.SITE + "/boardFileDownload.do", data={"bbs_id": bid, "seq_no": seq}, headers={**k.UA, "Referer": k.SITE + f"/boardView.do?bbs_id={bid}&menuId=57"}, timeout=60)
        except Exception as e:  # noqa: BLE001
            log("F", bid, seq, "ERR", type(e).__name__)
            continue
        is_pdf = r.content[:4] == b"%PDF"
        log("F", bid, name, seq, r.status_code, r.headers.get("Content-Type"), len(r.content), "PDF" if is_pdf else "")
        if not is_pdf:
            continue
        text, err = k.pdf_text(r.content)
        if err:
            log("   PDF", err)
            break
        t = re.sub(r"\s+", " ", text or "")
        hits = [t[max(0, m.start() - 110):m.end() + 25] for m in re.finditer(r"신청", t)][:4]
        for h in hits:
            log("   ctx:", h)
        if not hits:
            log("   head:", t[:250])
        break
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
