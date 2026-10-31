"""Probe 20: NHTSA 소비자 결함 신고(2025-2026 파일) — 현대·기아·제네시스 차종×부품(윗단계)별 최근 28일 신고 수와 지난 24주 평균,
화재·충돌·부상 수, 같은 신고 번호(ODINO)의 부품 줄 수. 문턱 정하기용. 저장하지 않음. 키 없음."""
import collections
import datetime as dt
import io
import zipfile
import requests

out = []
UA = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
r = requests.get("https://static.nhtsa.gov/odi/ffdd/cmpl/COMPLAINTS_RECEIVED_2025-2026.zip", headers=UA, timeout=300)
z = zipfile.ZipFile(io.BytesIO(r.content))
rows = [ln.split("\t") for ln in z.read(z.namelist()[0]).decode("latin-1").splitlines()]
last = max(x[15] for x in rows if len(x) > 15 and x[15][:2] == "20")
end = dt.datetime.strptime(last, "%Y%m%d").date()
out.append(f"rows {len(rows)} last DATEA {last} file-mod {r.headers.get('last-modified')}")
mk = ("HYUNDAI", "KIA", "GENESIS")
odi_rows = collections.Counter(x[1] for x in rows if len(x) > 15 and x[3].upper() in mk)
out.append("rows per ODINO (hyundai group): " + repr(collections.Counter(odi_rows.values()).most_common(6)))
recent_cut = end - dt.timedelta(days=28)
base_cut = recent_cut - dt.timedelta(days=168)
rec = collections.defaultdict(set); base = collections.defaultdict(set); fire = collections.defaultdict(set); crash = collections.defaultdict(set); inj = collections.defaultdict(set)
years = collections.defaultdict(collections.Counter)
weekly = collections.Counter()
for x in rows:
    if len(x) < 20 or x[3].upper() not in mk:
        continue
    try:
        d = dt.datetime.strptime(x[15], "%Y%m%d").date()
    except ValueError:
        continue
    comp = x[11].split(":")[0].strip() or "?"
    key = (x[3].upper(), x[4].upper(), comp)
    if d > recent_cut:
        rec[key].add(x[1]); years[key][x[5]] += 1
        if x[8] == "Y": fire[key].add(x[1])
        if x[6] == "Y": crash[key].add(x[1])
        if (x[9] or "0") not in ("0", ""): inj[key].add(x[1])
    elif d > base_cut:
        base[key].add(x[1])
    weekly[(d - dt.date(2025, 1, 1)).days // 7] += 1
out.append("weekly totals (last 12 weeks): " + repr(sorted(weekly.items())[-12:]))
cand = []
for key, s in rec.items():
    b = len(base[key]) / 6.0
    cand.append((len(s), b, key))
cand.sort(key=lambda c: (-(c[0] / max(c[1], 1.0)), -c[0]))
out.append("TOP by ratio (recent>=6): ")
for n, b, key in [c for c in cand if c[0] >= 6][:25]:
    out.append(f"  {key[0]} {key[1]} | {key[2]} | 28d {n} vs base/28d {b:.1f} | fire {len(fire[key])} crash {len(crash[key])} inj {len(inj[key])} | yrs {dict(years[key].most_common(3))}")
out.append("TOP by count: ")
for n, b, key in sorted(cand, key=lambda c: -c[0])[:15]:
    out.append(f"  {key[0]} {key[1]} | {key[2]} | 28d {n} vs base/28d {b:.1f} | fire {len(fire[key])}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:400])
