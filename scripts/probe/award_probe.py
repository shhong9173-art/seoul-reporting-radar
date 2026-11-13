"""probe 225: 자동차리콜센터 무상점검·수리 게시판, 전파연구원 새 목록 쪽 넘김, NHTSA 제작사 정보(MID) 검색 꼴. 공개 페이지만, 저장 안 함."""
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
    OUT.append(f"## {label}: {r.status_code} {len(r.content)}바이트 ct={r.headers.get('content-type', '')[:40]}")
    return r.text or ""


# 1. 무상점검·수리
h = get("무상점검 목록", "https://www.car.go.kr/ri/grts/list.do", enc="utf-8")
body = h[h.find("container"):] if "container" in h else h
i = h.find("무상점검")
t = text_of(h)
j = t.find("서브메뉴")
OUT.append("   본문 글: " + t[t.find("무상점검", j + 400) if j >= 0 else 0:][:900])
OUT.append("   폼: " + " | ".join(f"{m[0]}={m[1][:20]}" for m in re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', h)[:20]))
OUT.append("   select: " + " | ".join(re.findall(r'<select[^>]*name="([^"]+)"', h)[:10]))
OUT.append("   함수: " + " | ".join(dict.fromkeys(re.findall(r"(fn_[A-Za-z0-9_]+)\(", h)))[:300])
OUT.append("   onclick: " + " | ".join(dict.fromkeys(re.findall(r'onclick="([^"]{5,90})"', h)))[:600])
OUT.append("   href: " + " | ".join(dict.fromkeys(x for x in re.findall(r'href="([^"]+)"', h) if "grts" in x or "view" in x.lower()))[:500])
for m in re.finditer(r"<script[^>]*>([\s\S]*?)</script>", h):
    sc = m.group(1)
    if "grts" in sc or "ajax" in sc.lower() or "submit" in sc:
        OUT.append("   스크립트: " + re.sub(r"\s+", " ", sc)[:900])
k = h.find("<ul", h.find("sub_cont") if "sub_cont" in h else 0)
m = re.search(r'<(?:ul|div)[^>]*class="[^"]*(?:list|board|tbl)[^"]*"[^>]*>([\s\S]{0,1500})', h)
OUT.append("   목록 원문: " + re.sub(r"\s+", " ", m.group(0) if m else h[len(h) // 2:len(h) // 2 + 1200])[:1400])
h2 = get("무상점검 2쪽", "https://www.car.go.kr/ri/grts/list.do?currentPageNo=2", enc="utf-8")
OUT.append("   2쪽 글: " + text_of(h2)[text_of(h2).find("서브메뉴") + 400:][:300])
# 2. 전파연구원 새 목록
h = get("RRA 새 목록 2쪽", "https://www.rra.go.kr/ko/license/A_b_newlist.do?cpage=2", enc="euc-kr")
rows = re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", h, re.I)
OUT.append(f"   줄 {len(rows)} · " + " / ".join(" ¦ ".join(text_of(c)[:22] for c in re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", r, re.I)) for r in rows[1:4]))
OUT.append("   쪽 링크: " + " | ".join(dict.fromkeys(re.findall(r'href="([^"]*newlist[^"]*)"', h)))[:300] + " // " + " | ".join(dict.fromkeys(re.findall(r"(?:goPage|fn_page|page)\(['\"]?(\d+)", h)))[:80])
h = get("RRA 새 목록 원문", "https://www.rra.go.kr/ko/license/A_b_newlist.do", enc="euc-kr")
m = re.search(r"<tr[^>]*>(?:(?!</tr>)[\s\S])*적합등록[\s\S]*?</tr>", h)
OUT.append("   행 원문: " + re.sub(r"\s+", " ", m.group(0) if m else "")[:700])
OUT.append("   폼: " + " | ".join(re.findall(r'<(?:input|select)[^>]*name="([^"]+)"', h)[:25]))
# 3. NHTSA MID
h = get("MID 첫 화면", "https://vpic.nhtsa.dot.gov/mid/", enc="utf-8")
OUT.append("   폼: " + " | ".join(re.findall(r'<form[^>]*action="([^"]*)"', h)) + " // 입력: " + " | ".join(re.findall(r'<(?:input|select)[^>]*name="([^"]+)"', h)[:25]))
OUT.append("   경로: " + " | ".join(dict.fromkeys(re.findall(r"['\"](/mid/[A-Za-z0-9_/?=&.-]+)['\"]", h)))[:600])
OUT.append("   글: " + text_of(h)[500:1100])
h = get("MID 검색(Hyundai)", "https://vpic.nhtsa.dot.gov/mid/home/search?name=Hyundai", enc="utf-8")
OUT.append("   글: " + text_of(h)[300:800])
h = get("vPIC API 제작사(Hyundai)", "https://vpic.nhtsa.dot.gov/api/vehicles/GetManufacturerDetails/hyundai?format=json", enc="utf-8")
OUT.append("   앞: " + h[:500])
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
