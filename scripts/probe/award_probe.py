"""probe 228: 자동차리콜센터 robots.txt·무상점검 상세 GET 주소, 전파연구원 robots.txt·새 목록 줄 꼴. 공개 페이지만, 저장 안 함."""
import re

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
OUT = []
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "ko,en;q=0.8"})


def text_of(html):
    t = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", html or "", flags=re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t)).strip()


def robots(host):
    try:
        r = S.get(f"https://{host}/robots.txt", timeout=30)
        body = (r.text or "")
        kind = "HTML" if "<html" in body[:400].lower() else "글"
        OUT.append(f"## robots {host}: {r.status_code} {r.headers.get('content-type')} {len(body)}자 {kind}")
        if r.status_code == 200 and kind == "글":
            OUT.append("   " + " | ".join(x.strip() for x in body.splitlines() if x.strip())[:700])
    except Exception as e:  # noqa: BLE001
        OUT.append(f"## robots {host}: 실패 {type(e).__name__}")


robots("www.car.go.kr")
h = S.get("https://www.car.go.kr/ri/grts/list.do", timeout=40)
h.encoding = "utf-8"
ids = re.findall(r"detailView\('(\d+)','(\w)'\)", h.text)
OUT.append(f"## 목록 {h.status_code} 글 번호 {ids[:5]}")
m = re.search(r"detailView\s*[:=]\s*function\s*\(([^)]*)\)\s*\{([\s\S]{0,700})", h.text)
OUT.append("   detailView: " + (re.sub(r"\s+", " ", m.group(0))[:600] if m else "함수 못 찾음"))
for src in re.findall(r'<script[^>]+src="([^"]+)"', h.text)[:30]:
    if "grts" in src or "main" in src.lower():
        OUT.append("   script: " + src[:160])
if ids:
    nid, ty = ids[0]
    for label, url in (("GET 쿼리", f"https://www.car.go.kr/ri/grts/detail.do?gratischeckId={nid}&ctype={ty}"),
                       ("GET 쿼리+쪽", f"https://www.car.go.kr/ri/grts/detail.do?gratischeckId={nid}&ctype={ty}&currentPageNo=1")):
        try:
            d = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "ko"}, timeout=40, allow_redirects=False)
            d.encoding = "utf-8"
            t = text_of(d.text)
            has = [k for k in ("제작(수입)사", "차명", "생산기간", "대수", "무상점검내용", "조치사항") if k in t]
            OUT.append(f"## 상세 {label} {d.status_code} {len(d.content)}바이트 Location={d.headers.get('location')} 표 낱말 {has}")
        except Exception as e:  # noqa: BLE001
            OUT.append(f"## 상세 {label}: 실패 {type(e).__name__}")
robots("www.rra.go.kr")
for page in (1, 2, 40, 88):
    try:
        r = S.get(f"https://www.rra.go.kr/ko/license/A_b_newlist.do?cpage={page}", timeout=40)
        r.encoding = "euc-kr"
        rows = re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", r.text, re.I)
        pages = re.findall(r"cpage=(\d+)", r.text)
        OUT.append(f"## RRA 새 목록 {page}쪽: {r.status_code} 줄 {len(rows)} 쪽 링크 최대 {max(map(int, pages)) if pages else '?'}")
        for x in rows[:1] + rows[1:4]:
            cells = [text_of(c)[:34] for c in re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", x, re.I)]
            link = re.search(r"app_no=(\d+)", x)
            OUT.append("   " + " ¦ ".join(cells) + (f" ¦ app_no {link.group(1)}" if link else ""))
    except Exception as e:  # noqa: BLE001
        OUT.append(f"## RRA 새 목록 {page}쪽: 실패 {type(e).__name__}")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
