"""Probe 55: nhtsa_tsbs.collect 실제 파일 드라이런 — 건수·종류×등급·회사별·시간·메모리, NHTSA ID 꼴, 문서 PDF 주소 꼴(상태 코드만). 내용·차명은 찍지 않는다."""
import collections
import datetime as dt
import resource
import sys
import time
import requests

sys.path.insert(0, "scripts")
import nhtsa_tsbs as T

H = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []
now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
t0 = time.time()
doc, check = T.collect(now, None, get=requests.get)
out.append(f"check {check['status']} rows={check.get('rows')} err={check.get('error')} mod={check.get('fileModified')} secs={time.time() - t0:.0f} "
           f"maxrssMB={resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024} spans={T.spans(now)}")
items = doc.get("items") or []
out.append(f"items={len(items)} seen={len(doc.get('seen') or [])}")
out.append("type x tier: " + str(sorted(collections.Counter((x['type'], x['tier']) for x in items).items())))
out.append("company x tier: " + str(sorted(collections.Counter((','.join(x['companies']), x['tier']) for x in items).items())))
out.append("added by month: " + str(sorted(collections.Counter(x['added'][:7] for x in items).items())))
out.append("modelCount dist: " + str(sorted(collections.Counter(min(x['modelCount'], 10) for x in items).items())))
out.append("summary len max/median: " + str(max((len(x['summary']) for x in items), default=0)) + "/" + str(sorted(len(x['summary']) for x in items)[len(items) // 2] if items else 0))
out.append("replaces nonempty: " + str(sum(1 for x in items if x.get('replaces'))))
out.append("campaign nonempty: " + str(sum(1 for x in items if x.get('campaign'))))
out.append("id shapes: " + str(collections.Counter((len(x['id']), x['id'].isdigit(), x['id'][:3] if not x['id'][:1].isdigit() else 'num') for x in items).most_common(4)))
out.append("doc shapes: " + str(collections.Counter(('alpha' if x['doc'][:1].isalpha() else 'num', len(x['doc'])) for x in items).most_common(4)))
# 문서 PDF 주소 꼴 시험(앞 3건 × 꼴 2개, 2초 간격, 상태 코드만)
pats = ["https://static.nhtsa.gov/odi/tsbs/{ya}/MC-{id}-0001.pdf", "https://static.nhtsa.gov/odi/tsbs/{ym}/MC-{id}-0001.pdf"]
for x in items[:3]:
    res = []
    for p in pats:
        u = p.format(ya=x['added'][:4], ym=(x.get('mfrDate') or x['added'])[:4], id=x['id'])
        try:
            r = requests.head(u, headers=H, timeout=30, allow_redirects=True)
            res.append(f"{r.status_code}:{r.headers.get('Content-Type', '')[:20]}")
        except Exception as e:  # noqa: BLE001
            res.append(type(e).__name__)
        time.sleep(2)
    out.append(f"pdf patterns {res} (added y==mfr y: {x['added'][:4] == (x.get('mfrDate') or '')[:4]})")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
