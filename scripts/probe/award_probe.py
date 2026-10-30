"""probe: 광명·광주 서구·광산구 새올 목록 HTML 모양(표 부분만, 공개 자료)."""
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kr_local_notice_watch as w  # noqa: E402

out = []
for label, base in (("광명", "https://eminwon.gm.go.kr"), ("광주 서구", "https://eminwon.seogu.gwangju.kr"), ("광산구", "https://eminwon.gwangsan.go.kr")):
    try:
        r = requests.post(base + w.PATH, data={**w.LIST, "pageIndex": "1"}, headers={**w.UA, "Referer": base + w.PATH}, timeout=75)
        t = r.text
        rows = w.parse_rows(t)
        out.append(f"== {label} HTTP {r.status_code} len {len(t)} enc {r.encoding} rows {len(rows)} sample {[(x['no'], x['title'][:30], x['date']) for x in rows[:3]]}")
        i = t.find("<tbody")
        seg = t[i:i + 1600] if i >= 0 else t[:1600]
        out.append(re.sub(r"\s+", " ", seg))
        if i < 0:
            out.append("forms: " + " ".join(re.findall(r"<form[^>]*>", t)[:3]) + " | title: " + " ".join(re.findall(r"<title>(.*?)</title>", t, re.S)[:1]))
    except Exception as e:  # noqa: BLE001
        out.append(f"ERR {label} {type(e).__name__}")
blob = "\n".join(out)
open("/tmp/probe_out.txt", "w").write(blob)
print("total chars", len(blob))
