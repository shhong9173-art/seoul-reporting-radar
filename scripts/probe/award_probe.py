"""Probe 77: 정책브리핑(korea.kr) 부처별 보도자료 RSS — GitHub 러너에서 열리는지, 줄 수·최근 제목 몇 줄(공개 보도자료).
공정위·기후에너지환경부·산업통상부·국토교통부 RSS 주소 후보를 한 번씩만. robots.txt도 한 번 읽어 RSS 경로 허용 여부를 본다."""
import re
import xml.etree.ElementTree as ET

import requests

H = {"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []
try:
    rb = requests.get("https://www.korea.kr/robots.txt", headers=H, timeout=30)
    out.append(f"robots HTTP {rb.status_code}: " + re.sub(r"\s+", " ", rb.text[:400]))
except Exception as e:  # noqa: BLE001
    out.append(f"robots {type(e).__name__}")
for name, url in [("공정위", "https://www.korea.kr/rss/dept_ftc.xml"), ("기후에너지환경부", "https://www.korea.kr/rss/dept_me.xml"),
                  ("산업통상부", "https://www.korea.kr/rss/dept_motie.xml"), ("보도자료 전체", "https://www.korea.kr/rss/pressrelease.xml")]:
    try:
        r = requests.get(url, headers=H, timeout=30)
        out.append(f"{name} {url} HTTP {r.status_code} len {len(r.text)} ctype {r.headers.get('content-type')}")
        if r.status_code == 200:
            try:
                root = ET.fromstring(r.content)
                items = root.findall("./channel/item")
                out.append(f"  items {len(items)}")
                for it in items[:5]:
                    out.append(f"  {(it.findtext('pubDate') or '')[:25]} | {(it.findtext('title') or '')[:70]}")
            except ET.ParseError as e:
                out.append(f"  not XML {e}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{name} {type(e).__name__} {str(e)[:80]}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:600])
