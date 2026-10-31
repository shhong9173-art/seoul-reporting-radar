"""Probe 54: NHTSA 제조사 통신 TSV(TSBS_RECEIVED_2025-2026.zip) — 필드 목록, 현대·기아·제네시스 건수·통신 종류·추가일 분포·부품 분포(범주만)."""
import collections
import io
import time
import zipfile
import requests

H = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []
r = requests.get("https://static.nhtsa.gov/odi/ffdd/tsbs/TSBS.txt", headers=H, timeout=60)
t = r.text
out.append(t[t.find("FIELDS"):][:2600])
time.sleep(2)
z = requests.get("https://static.nhtsa.gov/odi/ffdd/tsbs/TSBS_RECEIVED_2025-2026.zip", headers=H, timeout=180)
zf = zipfile.ZipFile(io.BytesIO(z.content))
out.append(f"zip files: {[(i.filename, i.file_size) for i in zf.infolist()]}")
name = zf.infolist()[0].filename
raw = zf.read(name)
text = raw.decode("utf-8", "replace")
lines = text.splitlines()
out.append(f"lines={len(lines)} first-line-cols={len(lines[0].split(chr(9)))}")
rows = [ln.split("\t") for ln in lines if ln.strip()]
ncol = collections.Counter(len(x) for x in rows).most_common(3)
out.append(f"col counts {ncol}")
# guess columns by scanning first row values (print types/lengths only)
first = rows[0]
out.append("first row value shapes: " + " | ".join(f"{i}:{(v[:12] if len(v) < 14 and not any(c.isalpha() for c in v[:3]) else ('TXT' + str(len(v))))}" for i, v in enumerate(first)))
makes = collections.Counter()
for x in rows:
    for v in x:
        if v.strip().upper() in ("HYUNDAI", "KIA", "GENESIS"):
            makes[v.strip().upper()] += 1
            break
out.append(f"rows with HYUNDAI/KIA/GENESIS in some column: {dict(makes)}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
