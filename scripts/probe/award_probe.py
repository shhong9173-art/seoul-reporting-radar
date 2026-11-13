"""probe 226: 무상점검·수리 상세 주소와 본문 꼴, 전파연구원 새 목록의 검색 인자. 공개 페이지만, 저장 안 함."""
import re

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
OUT = []
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "ko,en;q=0.8"})


def text_of(html):
    t = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", html or "", flags=re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t)).strip()


def get(label, url, enc=None, method="GET", data=None, timeout=40):
    try:
        r = S.request(method, url, data=data, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        OUT.append(f"## {label}: 실패 {type(e).__name__} {str(e)[:80]}")
        return ""
    if enc:
        r.encoding = enc
    OUT.append(f"## {label}: {r.status_code} {len(r.content)}바이트 끝주소={r.url[:100]}")
    return r.text or ""


h = get("무상점검 목록", "https://www.car.go.kr/ri/grts/list.do", enc="utf-8")
srcs = re.findall(r'<script[^>]*src="([^"]+)"', h)
OUT.append("   스크립트 파일: " + " | ".join(s[:70] for s in srcs))
for m in re.finditer(r"<script[^>]*>([\s\S]*?)</script>", h):
    sc = m.group(1)
    if "detailView" in sc:
        i = sc.find("detailView")
        OUT.append("   detailView 둘레: " + re.sub(r"\s+", " ", sc[max(0, i - 200):i + 900]))
for src in srcs:
    if re.search(r"grts|ri/|list|board", src, re.I):
        js = get(f"js {src[-40:]}", "https://www.car.go.kr" + src if src.startswith("/") else src, enc="utf-8")
        i = js.find("detailView")
        if i >= 0:
            OUT.append("   detailView 둘레: " + re.sub(r"\s+", " ", js[max(0, i - 100):i + 700]))
ids = re.findall(r"detailView\('(\d+)','(\w)'\)", h)
OUT.append(f"   글 번호: {ids[:6]}")
if ids:
    nid, ty = ids[0]
    for label, url, data in (("view GET seq", f"https://www.car.go.kr/ri/grts/view.do?seq={nid}&ctype={ty}", None),
                             ("view GET ntceSn", f"https://www.car.go.kr/ri/grts/view.do?ntceSn={nid}", None),
                             ("view POST", "https://www.car.go.kr/ri/grts/view.do", {"seq": nid, "ctype": ty, "currentPageNo": "1"}),
                             ("detail GET", f"https://www.car.go.kr/ri/grts/detail.do?seq={nid}&ctype={ty}", None)):
        d = get(label, url, enc="utf-8", method="POST" if data else "GET", data=data)
        t = text_of(d)
        j = t.find("무상수리")
        OUT.append("   글: " + (t[t.find("서브메뉴") + 380:][:700] if "서브메뉴" in t else t[:300]))
# 전파연구원: 새 목록 검색
for con in ("1", "2", "3", "firm", "company"):
    h = get(f"RRA 새 목록 검색 searchCon={con}", f"https://www.rra.go.kr/ko/license/A_b_newlist.do?cpage=1&searchCon={con}&searchTxt=%C7%F6%B4%EB", enc="euc-kr")
    rows = re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", h, re.I)
    OUT.append(f"   줄 {len(rows)} · " + " / ".join(" ¦ ".join(text_of(c)[:18] for c in re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", r, re.I)) for r in rows[1:3]))
h = get("RRA 새 목록", "https://www.rra.go.kr/ko/license/A_b_newlist.do", enc="euc-kr")
m = re.search(r'<select[^>]*name="searchCon"[^>]*>([\s\S]*?)</select>', h)
OUT.append("   searchCon 선택지: " + re.sub(r"\s+", " ", m.group(1) if m else "없음")[:300])
OUT.append("   총 건수 글: " + " | ".join(re.findall(r"(?:총|전체)[^<]{0,30}건", h)[:3]) + " // 마지막 쪽: " + " ".join(re.findall(r"cpage=(\d+)", h)[-3:]))
p = get("RRA 팝업", "https://www.rra.go.kr/ko/license/A_b_popup.do?app_no=202617210000428607", enc="euc-kr")
OUT.append("   팝업 글: " + text_of(p)[:500])
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
