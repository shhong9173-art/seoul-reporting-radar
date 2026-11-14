"""probe 244: CITT 한국 사건 표의 줄 마크업(th/td) 확인. 공개 페이지만, 저장 안 함."""
import re

import requests

OUT = []
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36", "Accept-Language": "en-CA,en;q=0.9"}
r = requests.get("https://www.citt-tcce.gc.ca/en/anti-dumping-injury-inquiries/active-dumping-and-subsidizing-cases", headers=H, timeout=60)
m = (re.search(r"<main\b.*?</main>", r.text, re.S | re.I) or [r.text])[0]
n = 0
for t in re.finditer(r"<table\b.*?</table>", m, re.S | re.I):
    tb = t.group(0)
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S | re.I)
    shape = ["".join(c[0].lower() + ("r" if 'scope="row"' in c[1] else "c" if 'scope="col"' in c[1] else "") + " " for c in re.findall(r"<(t[hd])\b([^>]*)>", x, re.I)).strip() for x in rows]
    n += 1
    if "Korea" in tb:
        OUT.append("한국 표 원문(공백 정리): " + re.sub(r"\s+", " ", tb)[:1500])
        OUT.append("한국 표 줄 모양: " + " | ".join(shape))
    else:
        OUT.append(f"표{n} 줄 모양: " + " | ".join(shape)[:160])
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
