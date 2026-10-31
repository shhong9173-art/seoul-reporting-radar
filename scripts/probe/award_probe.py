"""Probe 19: (a) NHTSA 소비자 결함 신고 파일(공개 flat file) 이름·크기·필드·최신 접수일, 현대·기아·제네시스 최근 60일 건수.
(b) 무공해차 통합누리집 보조금 대상 차종 쪽이 GitHub에서 열리는지. 저장하지 않음. 키 없음."""
import collections
import csv
import datetime as dt
import io
import re
import zipfile
import requests

out = []
UA = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
BASE = "https://static.nhtsa.gov/odi/ffdd/cmpl/"
names = ["COMPLAINTS_RECEIVED_2025-2026.zip", "COMPLAINTS_RECEIVED_2026-2026.zip", "COMPLAINTS_RECEIVED_2026.zip", "FLAT_CMPL.zip", "Import_Instructions_Complaints.pdf"]
found = None
for n in names:
    try:
        r = requests.head(BASE + n, headers=UA, timeout=30, allow_redirects=True)
        out.append(f"HEAD {n}: {r.status_code} len={r.headers.get('content-length')} mod={r.headers.get('last-modified')}")
        if r.status_code == 200 and n.startswith("COMPLAINTS_RECEIVED_2025") and not found:
            found = n
    except Exception as e:  # noqa: BLE001
        out.append(f"HEAD {n}: {type(e).__name__} {e}"[:200])
try:
    r = requests.get("https://www.nhtsa.gov/nhtsa-datasets-and-apis", headers=UA, timeout=30)
    out.append(f"datasets page {r.status_code}: " + ", ".join(sorted(set(re.findall(r"ffdd/cmpl/[A-Za-z0-9_.-]+", r.text))))[:600])
except Exception as e:  # noqa: BLE001
    out.append(f"datasets page {type(e).__name__}")
if found:
    r = requests.get(BASE + found, headers=UA, timeout=240)
    out.append(f"GET {found}: {r.status_code} {len(r.content)} bytes")
    z = zipfile.ZipFile(io.BytesIO(r.content))
    out.append("members: " + repr([(i.filename, i.file_size) for i in z.infolist()]))
    member = z.infolist()[0].filename
    text = z.read(member).decode("latin-1")
    lines = text.splitlines()
    out.append(f"lines {len(lines)}; first: {lines[0][:600]!r}")
    rows = [ln.split("\t") for ln in lines]
    out.append("cols per row: " + repr(collections.Counter(len(r) for r in rows[:2000]).most_common(3)))
    # guess date-added column: find col values like YYYYMMDD
    sample = rows[-1]
    out.append("last row: " + repr(sample[:30])[:1200])
    dates = collections.Counter()
    for c in range(len(sample)):
        v = [r[c] for r in rows[-500:] if len(r) > c]
        if v and sum(bool(re.fullmatch(r"20\d{6}", x)) for x in v) > 400:
            dates[c] = max(v)
    out.append("date-like cols (max): " + repr(dict(dates)))
    mk = collections.Counter()
    recent = collections.Counter()
    for r in rows:
        if len(r) > 4 and r[3].upper() in ("HYUNDAI", "KIA", "GENESIS"):
            mk[r[3].upper()] += 1
    out.append("make counts (col3): " + repr(mk))
open("/tmp/probe_out.txt", "w").write("\n".join(out))
for u in ["https://ev.or.kr/nportal/buySupprt/initSubsidyPaymentCheckAction.do", "https://ev.or.kr/nportal/buySupprt/initPsLocalCarPirceAction.do",
          "https://ev.or.kr/nportal/main.do"]:
    try:
        r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        t = r.text
        out.append(f"EV {u}: {r.status_code} len={len(t)} 아이오닉={t.count('아이오닉')} EV3={t.count('EV3')} title={re.search(r'<title>(.*?)</title>', t, re.S).group(1).strip()[:60] if '<title>' in t else '-'}")
    except Exception as e:  # noqa: BLE001
        out.append(f"EV {u}: {type(e).__name__} {str(e)[:120]}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:400])
