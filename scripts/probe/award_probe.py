"""Probe 17: 새올 지자체 고시·공고 상세 페이지 형식 — 목록 제목이 '...'로 잘리는 공고의 전체 제목·본문이 상세에 있는지. robots.txt 먼저. 공개 자료, 저장하지 않음."""
import re
import sys
import time
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kr_local_notice_watch as w  # noqa: E402

out = []
for base, mgt in [("http://eminwon.ulju.ulsan.kr", "68156"), ("https://eminwon.wanju.go.kr", "44869")]:
    try:
        rb = requests.get(base + "/robots.txt", headers=w.UA, timeout=30)
        out.append(f"== {base} robots {rb.status_code}: {rb.text[:300]!r}")
    except Exception as e:  # noqa: BLE001
        out.append(f"== {base} robots {type(e).__name__}")
    url = w.detail_url(base, mgt)
    try:
        r = requests.get(url, headers={**w.UA, "Referer": base + w.PATH}, timeout=75)
        html = r.text
        out.append(f"detail {mgt} HTTP {r.status_code} len {len(html)} charset {r.encoding}")
        # 표 칸(th/td) 쌍과 본문
        cells = [w.cell_text(c) for c in re.findall(r"<t[hd][^>]*>([\s\S]*?)</t[hd]>", html)]
        out.append("cells: " + " | ".join(c[:160] for c in cells if c)[:2500])
        text = w.cell_text(re.sub(r"<(script|style)[\s\S]*?</\1>", " ", html))
        i = text.find("고려아연") if "고려아연" in text else text.find("공고")
        out.append("text@: " + text[max(0, i - 300):i + 1500])
        files = re.findall(r"(?:fileDown|download|atchFile)[^\"'<>]{0,200}", html)[:5]
        out.append("files: " + " ;; ".join(files))
    except Exception as e:  # noqa: BLE001
        out.append(f"detail {mgt} {type(e).__name__}: {str(e)[:120]}")
    time.sleep(2)
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:500])
