"""Probe 16: 해외 공식 페이지 감시 대상이 다른 주소로 넘어가는지(리디렉트) — 최종 주소·제목. 공개 자료, 저장하지 않음."""
import json
import re
import sys
import time
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import page_watch as pw  # noqa: E402

cfg = json.loads(Path("data/official_page_watch.json").read_text(encoding="utf-8"))
out = []
for p in cfg.get("pages") or cfg.get("targets") or []:
    url = p["url"]
    try:
        r = requests.get(url, headers=pw.HEADERS, timeout=30, allow_redirects=True)
        title = re.sub(r"\s+", " ", (re.search(r"<title[^>]*>(.*?)</title>", r.text, re.S | re.I) or [None, ""])[1]).strip()[:90]
        canon = (re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', r.text, re.I) or [None, ""])[1]
        hist = " > ".join(f"{h.status_code}:{h.headers.get('location', '')[:80]}" for h in r.history)
        out.append(f"{p['id']} | {r.status_code} | final {r.url} | hist {hist or '-'} | canonical {canon[:90]} | title {title}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{p['id']} | {type(e).__name__}")
    time.sleep(1.5)
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:300])
