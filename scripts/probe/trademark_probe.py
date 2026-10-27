"""One KIPRIS Plus trademark call (isolated). Prints result code, counts and field names only — never the key."""
import datetime as dt
import os
import re
import requests

KEY = os.environ.get("KIPRIS_SERVICE_KEY", "").strip()
OUT = [f"key {'set' if KEY else 'missing'} len={len(KEY)}"]
end = dt.date.today()
start = end - dt.timedelta(days=60)
flags = {k: "true" for k in ("application", "registration", "refused", "expiration", "withdrawal", "publication", "cancel", "abandonment",
                             "trademark", "serviceMark", "businessEmblem", "collectiveMark", "geoOrgMark", "trademarkServiceMark", "certMark",
                             "geoCertMark", "internationalMark", "character", "figure", "compositionCharacter", "figureComposition", "fragrance",
                             "sound", "color", "colorMixed", "dimension", "hologram", "invisible", "motion", "visual")}
if KEY:
    r = requests.get("https://plus.kipris.or.kr/kipo-api/kipi/trademarkInfoSearchService/getAdvancedSearch",
                     params={"applicantName": "현대자동차주식회사", "applicationDate": f"{start:%Y%m%d}~{end:%Y%m%d}", "numOfRows": 20, "pageNo": 1,
                             **flags, "ServiceKey": KEY}, timeout=40)
    t = r.text
    OUT.append(f"HTTP {r.status_code} len {len(t)}")
    for tag in ("successYN", "resultCode", "resultMsg", "totalCount"):
        m = re.search(rf"<{tag}>([^<]*)</{tag}>", t)
        OUT.append(f"{tag}={m.group(1) if m else None}")
    items = re.findall(r"<item>(.*?)</item>", t, re.S)
    OUT.append(f"items {len(items)}")
    for it in items[:8]:
        g = lambda k: (re.search(rf"<{k}>([^<]*)</{k}>", it) or [None, ""])[1]
        OUT.append(f"{g('applicationDate')} {g('applicationNumber')} [{g('applicationStatus')}] {g('title')} cls={g('classificationCode')} ap={g('applicantName')}")
clean = [o.replace("\r", " ").replace("\n", " ").replace("%", "pct").replace("::", ": :") for o in OUT]
for i in range(0, len(clean), 6):
    print(f"::notice title=tm-{i // 6:02d}::" + " | ".join(clean[i:i + 6])[:3900])
