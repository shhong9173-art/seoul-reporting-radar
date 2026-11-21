"""정책브리핑 보도자료 목록의 부처 코드 — 고용노동부 코드 찾기(요청 2~3번, 2초 간격, 제목은 건수만)"""
import re, time, html, requests
UA = {"User-Agent": "Mozilla/5.0 seoul-reporting-radar (reporter research)"}
B = "https://www.korea.kr/briefing/pressReleaseList.do"
r = requests.get(B, headers=UA, timeout=30)
print("list", r.status_code, len(r.text))
codes = {}
for m in re.finditer(r"repCode(?:Type)?['\"=:,\s]+['\"]?([AB]\d{5})['\"]?[^<>]{0,200}?>\s*([^<]{2,20})<", r.text):
    codes.setdefault(m.group(1), html.unescape(m.group(2)).strip())
for m in re.finditer(r"([AB]\d{5})", r.text):
    i = m.start()
    near = re.sub(r"<[^>]+>", " ", r.text[i:i + 160])
    near = re.sub(r"\s+", " ", html.unescape(near))
    if "노동" in near or "고용" in near:
        print("NEAR", m.group(1), near[:120])
print({k: v for k, v in codes.items() if "노동" in v or "고용" in v or "산업" in v})
print(len(codes))
for code in ["A00011", "A00012", "A00010"]:
    time.sleep(2)
    r2 = requests.get(B, params={"repCodeType": "A", "repCode": code, "pageIndex": 1}, headers=UA, timeout=30)
    mins = re.findall(r'<span class="source">\s*<span>\s*[\d.\-]+\s*</span>\s*<span>\s*([^<]+?)\s*</span>', r2.text)
    print("try", code, r2.status_code, sorted(set(mins))[:3], len(mins))
