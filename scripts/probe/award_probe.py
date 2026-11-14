"""probe 243: CITT 진행 사건 목록 — 표마다 앞에 붙은 사건 제목(태그·글자)과 구역. 공개 페이지만, 저장 안 함."""
import re

import requests

OUT = []
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36", "Accept-Language": "en-CA,en;q=0.9"}
r = requests.get("https://www.citt-tcce.gc.ca/en/anti-dumping-injury-inquiries/active-dumping-and-subsidizing-cases", headers=H, timeout=60)
m = (re.search(r"<main\b.*?</main>", r.text, re.S | re.I) or [r.text])[0]
txt = lambda x: re.sub(r"\s+", " ", re.sub(r"&nbsp;|&#160;", " ", re.sub(r"<[^>]+>", " ", x))).strip()
pos = 0
for i, t in enumerate(re.finditer(r"<table\b.*?</table>", m, re.S | re.I)):
    before = m[pos:t.start()]
    pos = t.end()
    tags = re.findall(r"<(h[1-6]|p|strong|caption|summary|details|li|a)\b", before, re.I)[-12:]
    heads = [(x.group(1), txt(x.group(2))[:150]) for x in re.finditer(r"<(h[1-6])\b[^>]*>(.*?)</\1>", before, re.S | re.I)]
    links = [h[-70:] for h in re.findall(r'href="([^"]+)"', before)][-3:]
    cap = txt((re.search(r"<caption\b.*?</caption>", t.group(0), re.S | re.I) or [""])[0])[:120]
    OUT.append(f"표{i}: 앞 글자 {len(txt(before))} · 태그 {tags} · 제목들 {heads[-3:]} · 캡션 「{cap}」 · 링크 {links}")
    OUT.append("     앞 글 끝: " + txt(before)[-330:])
OUT.append("Korea 위치 앞뒤: " + " ‖ ".join(txt(m[max(0, x.start() - 120):x.end() + 60]) for x in list(re.finditer("Korea", m))[:6]))
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
