"""Probe 56: 캠페인 묶음 등급 드라이런 — 묶음 수·등급×종류·회사×등급·문서 수 분포·월별 A/B. 내용·차명은 찍지 않는다."""
import collections
import datetime as dt
import json
import sys
import time
import requests

sys.path.insert(0, "scripts")
import nhtsa_tsbs as T

out = []
now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
t0 = time.time()
doc, check = T.collect(now, None, get=requests.get)
items = doc.get("items") or []
out.append(f"check {check['status']} docs={check.get('rows')} campaigns={check.get('campaigns')} kept={len(items)} secs={time.time() - t0:.0f} jsonKB={len(json.dumps(doc, ensure_ascii=False).encode()) // 1024}")
out.append("tier x kind: " + str(sorted(collections.Counter((x['tier'], x['kindName']) for x in items).items())))
out.append("company x tier: " + str(sorted(collections.Counter((','.join(x['companies']), x['tier']) for x in items).items())))
out.append("A/B by first-added month: " + str(sorted(collections.Counter((x['added'][:7], x['tier']) for x in items if x['tier'] in 'AB').items())))
out.append("docCount dist: " + str(sorted(collections.Counter(min(x['docCount'], 8) for x in items).items())))
out.append("key kinds: " + str(collections.Counter(x['id'].split(':')[1] if x['id'].count(':') > 1 else 'campaign' for x in items)))
out.append("renotice: " + str(sum(1 for x in items if x.get('renotice'))) + " gmShared: " + str(sum(1 for x in items if x.get('otherRows'))))
open("/tmp/probe_out.txt", "w").write("\n".join(out))
