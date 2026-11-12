"""probe 214: 무역위 보도자료 첨부 꼴(11-12) — PDF가 없는 보도자료의 첨부가 hwpx/hwp인지, 그 글자에서 신청인이 읽히는지.
공개 자료(무역위원회 보도자료). 저장 안 함. 요청 사이 0.8초. 한 번만 돈다."""
import re
import sys
import time

sys.path.insert(0, "scripts")
import requests  # noqa: E402
import ktc_watch as k  # noqa: E402
import kr_local_notice_watch as ln  # noqa: E402

OUT = []
http = k.Http(requests.Session())
rows = []
for page in range(1, 9):
    time.sleep(0.8)
    try:
        st, body = http.post(k.NEWS[0], {"menuId": k.NEWS[1], **({"pageIndex": str(page)} if page > 1 else {})})
    except Exception as e:  # noqa: BLE001
        OUT.append(f"LIST {page} {type(e).__name__}")
        continue
    got = k.parse_news(body) if st == 200 else []
    OUT.append(f"LIST {page} HTTP {st} rows {len(got)}")
    rows += [r for r in got if r["id"] not in {x["id"] for x in rows}]
want = [r for r in rows if k.APPLICANT_TITLE.search(r["title"])]
OUT.append(f"ROWS {len(rows)} · 제목 규칙에 맞는 것 {len(want)}")


def grab(bid, seq):
    time.sleep(0.8)
    try:
        st, body = http.post_binary("/boardFileDownload.do", {"bbs_id": bid, "seq_no": seq}, f"{k.SITE}/boardView.do?bbs_id={bid}&menuId={k.NEWS[1]}")
    except Exception as e:  # noqa: BLE001
        return None, type(e).__name__.encode()
    return st, body


def kind(body):
    h = body[:4]
    return "pdf" if h == b"%PDF" else "hwpx" if h[:2] == b"PK" else "hwp" if h == b"\xd0\xcf\x11\xe0" else f"기타({h.hex()},{len(body)}B)"


def text_of(body):
    try:
        if body[:2] == b"PK":
            return ln.hwpx_text(body), None
        if body[:4] == b"\xd0\xcf\x11\xe0":
            t = ln.hwp_text(body)
            return t, (None if t is not None else "olefile 없음")
    except Exception as e:  # noqa: BLE001
        return None, type(e).__name__
    return None, "형식 미상"


n_pdf = n_nopdf = compared = 0
kinds = {}
for r in want:
    bid = r["id"]
    seen = {}
    for seq in ("0001", "0000"):
        st, body = grab(bid, seq)
        seen[seq] = (st, body)
        if st == 200 and body[:4] == b"%PDF":
            break
    has_pdf = any(st == 200 and b[:4] == b"%PDF" for st, b in seen.values())
    if has_pdf:
        n_pdf += 1
        if compared < 5:            # PDF와 한글 첨부를 둘 다 읽어 신청인이 같게 나오는지(정답 대조)
            other = seen.get("0000") if "0000" in seen and seen["0000"][1][:4] != b"%PDF" else grab(bid, "0000")
            pdf_body = next(b for st, b in seen.values() if st == 200 and b[:4] == b"%PDF")
            pt, _ = k.pdf_text(pdf_body)
            pa = k.applicants_in(pt or "")
            if other[0] == 200 and other[1][:4] != b"%PDF":
                ht, herr = text_of(other[1])
                ha = k.applicants_in(ht or "")
                compared += 1
                same = [(a["product"], a["names"]) for a in pa] == [(a["product"], a["names"]) for a in ha]
                OUT.append(f"CMP {bid} {r['title'][:40]} | 0000={kind(other[1])} len {len(ht or '')} {herr or ''} | 같음 {same}")
                if not same:
                    OUT.append(f"    pdf : {pa!r}")
                    OUT.append(f"    hwp : {ha!r}")
        continue
    n_nopdf += 1
    for seq in ("0002", "0003"):
        st, body = grab(bid, seq)
        seen[seq] = (st, body)
        if st != 200 or len(body) < 200:
            break
    desc = []
    parsed = None
    for seq in sorted(seen):
        st, body = seen[seq]
        kd = kind(body) if st == 200 else f"HTTP {st}"
        kinds[kd.split("(")[0]] = kinds.get(kd.split("(")[0], 0) + 1
        desc.append(f"{seq}={kd}")
        if st == 200 and parsed is None and (body[:2] == b"PK" or body[:4] == b"\xd0\xcf\x11\xe0"):
            t, err = text_of(body)
            a = k.applicants_in(t or "")
            parsed = (len(t or ""), err, a)
            ctx = [re.sub(r"\s+", " ", t)[max(0, m.start() - 60):m.end() + 120] for m in re.finditer(r"\(\s*신청인\s*\)|신청인", t or "")][:2]
            desc.append(f"글자 {len(t or '')} {err or ''} 신청인 {a!r}")
            for c in ctx:
                desc.append("ctx: " + c)
        elif st == 200 and body[:1] in (b"<", b"\r", b"\n", b" "):
            desc.append("본문: " + re.sub(r"\s+", " ", body[:200].decode("utf-8", "ignore")))
    OUT.append(f"NOPDF {bid} {r['title'][:50]} | " + " | ".join(desc))
OUT.append(f"SUM pdf {n_pdf} · pdf 없음 {n_nopdf} · 첨부 꼴 {kinds}")
# PDF 없는 첫 글의 상세 화면에서 첨부 이름이 보이는지
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
