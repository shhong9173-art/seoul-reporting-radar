"""probe 227: 무상점검·수리 상세(POST detail.do) 본문 꼴, 전파연구원 새 목록 상호 검색. 공개 페이지만, 저장 안 함."""
import re
from urllib.parse import quote

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
OUT = []
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "ko,en;q=0.8"})


def text_of(html):
    t = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", html or "", flags=re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t)).strip()


h = S.get("https://www.car.go.kr/ri/grts/list.do", timeout=40)
h.encoding = "utf-8"
ids = re.findall(r"detailView\('(\d+)','(\w)'\)", h.text)
OUT.append(f"## 목록 {h.status_code} 글 번호 {ids[:5]}")
items = re.findall(r"detailView\('(\d+)','(\w)'\);\">\s*<strong>([\s\S]*?)</strong>[\s\S]*?<ol>([\s\S]*?)</ol>", h.text)
for nid, ty, title, meta in items[:5]:
    OUT.append(f"   {nid} {ty} ¦ {text_of(title)[:80]} ¦ {' / '.join(text_of(x) for x in re.findall(r'<li>([\s\S]*?)</li>', meta))}")
total = re.search(r"전체\s*([\d,]+)\s*건\s*\(페이지\s*(\d+)/(\d+)", text_of(h.text))
OUT.append(f"   전체 {total.groups() if total else '?'}")
if ids:
    nid, ty = ids[0]
    d = S.post("https://www.car.go.kr/ri/grts/detail.do", data={"gratischeckId": nid, "ctype": ty, "currentPageNo": "1", "searchFld": "", "searchWord": "", "searchFromDate": "", "searchToDate": ""},
               headers={"Referer": "https://www.car.go.kr/ri/grts/list.do"}, timeout=40)
    d.encoding = "utf-8"
    t = text_of(d.text)
    OUT.append(f"## 상세 POST {d.status_code} {len(d.content)}바이트")
    i = t.find("서브메뉴")
    OUT.append("   글: " + t[i + 380:i + 1700])
    OUT.append("   첨부: " + " | ".join(dict.fromkeys(re.findall(r'(?:href|onclick)="([^"]*(?:download|file|atch)[^"]*)"', d.text, re.I)))[:400])
    OUT.append("   표: " + " / ".join(" ¦ ".join(text_of(c)[:40] for c in re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", r, re.I)) for r in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", d.text, re.I)[:8])[:900])
    # 기아 K8 HEV 글(2쪽)
    h2 = S.post("https://www.car.go.kr/ri/grts/list.do", data={"currentPageNo": "2"}, timeout=40)
    h2.encoding = "utf-8"
    ids2 = re.findall(r"detailView\('(\d+)','(\w)'\);\">\s*<strong>([\s\S]*?)</strong>", h2.text)
    OUT.append(f"## 2쪽 POST {h2.status_code}: " + " | ".join(f"{a} {text_of(c)[:40]}" for a, b, c in ids2[:5]))
    kia = next(((a, b) for a, b, c in ids2 if "기아" in c or "현대" in c), None)
    if kia:
        d = S.post("https://www.car.go.kr/ri/grts/detail.do", data={"gratischeckId": kia[0], "ctype": kia[1], "currentPageNo": "2"}, timeout=40)
        d.encoding = "utf-8"
        t = text_of(d.text)
        i = t.find("서브메뉴")
        OUT.append(f"## 상세 {kia[0]} {d.status_code}: " + t[i + 380:i + 1900])
# 전파연구원 상호 검색
for name in ("현대자동차", "기아", "현대모비스", "비엠더블유"):
    try:
        r = S.get(f"https://www.rra.go.kr/ko/license/A_b_newlist.do?cpage=1&searchCon=PASSER&searchTxt={quote(name.encode('euc-kr'))}", timeout=40)
        r.encoding = "euc-kr"
        rows = re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", r.text, re.I)
        pages = re.findall(r"cpage=(\d+)", r.text)
        OUT.append(f"## RRA 상호={name}: {r.status_code} 줄 {len(rows) - 1} 마지막 쪽 {max(map(int, pages)) if pages else 1} · "
                   + " / ".join(" ¦ ".join(text_of(c)[:26] for c in re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", x, re.I)) for x in rows[1:5]))
    except Exception as e:  # noqa: BLE001
        OUT.append(f"## RRA 상호={name}: 실패 {type(e).__name__}")
p = S.get("https://www.rra.go.kr/ko/license/A_b_popup.do?app_no=202617210000428607", timeout=40)
cs = re.findall(r"charset=[^A-Za-z0-9]?([A-Za-z0-9-]+)", p.text[:600])
OUT.append(f"## RRA 팝업 {p.status_code} 문자셋 헤더 {p.headers.get('content-type')} 선언 {cs}")
p.encoding = "utf-8"
OUT.append("   글(utf-8): " + text_of(p.text)[:420])
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
