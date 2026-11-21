"""정책브리핑 고용노동부(A00001) 목록 제목 꼴(쪽 3개, 2초 간격) — 공개 보도자료 제목"""
import re, time, html, requests
UA = {"User-Agent": "Mozilla/5.0 seoul-reporting-radar (reporter research)"}
B = "https://www.korea.kr/briefing/pressReleaseList.do"
for page in (1, 2, 3):
    if page > 1:
        time.sleep(2)
    r = requests.get(B, params={"repCodeType": "A", "repCode": "A00001", "pageIndex": page}, headers=UA, timeout=30)
    for m in re.finditer(r'<a href="/briefing/pressReleaseView\.do\?newsId=(\d+)[^"]*"[^>]*>(.*?)</a>', r.text, re.S):
        t = re.search(r"<strong[^>]*>(.*?)</strong>", m.group(2), re.S)
        s = re.search(r'<span class="source">\s*<span>\s*([\d.\-]+)\s*</span>\s*<span>\s*([^<]+?)\s*</span>', m.group(2), re.S)
        if t and s:
            print(page, s.group(1), s.group(2).strip(), "|", html.unescape(re.sub(r"<[^>]+>", "", t.group(1))).strip()[:90])
