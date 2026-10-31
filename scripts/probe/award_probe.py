"""Probe 38: 나라장터 낙찰정보 HTML 응답 원인 — 같은 키로 입찰공고(작동 중) 대조, 낙찰 응답의 title·상태, XML/JSON 각각. 건수·태그·문구만."""
import os
import re
import time
import requests

KEY = os.environ.get("G2B_API_KEY", "").strip()
H = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []


def scrub(t):
    return t.replace(KEY, "<KEY>") if KEY else t


def show(label, url, params):
    try:
        r = requests.get(url, params={"serviceKey": KEY, **params}, headers=H, timeout=40)
    except Exception as e:  # noqa: BLE001
        out.append(f"{label}: {type(e).__name__}")
        return
    title = re.search(r"<title>(.*?)</title>", r.text, re.S)
    code = re.search(r"<resultCode>(.*?)</resultCode>|\"resultCode\"\s*:\s*\"(.*?)\"", r.text)
    msg = re.search(r"<resultMsg>(.*?)</resultMsg>|\"resultMsg\"\s*:\s*\"(.*?)\"|<returnAuthMsg>(.*?)</returnAuthMsg>", r.text)
    total = re.search(r"<totalCount>(\d+)</totalCount>|\"totalCount\"\s*:\s*(\d+)", r.text)
    out.append(f"{label}: HTTP {r.status_code} ctype={r.headers.get('content-type')} final={scrub(r.url.split('?')[0])} title={(title.group(1).strip()[:60] if title else None)!r} "
               f"code={next((g for g in (code.groups() if code else []) if g), None)} msg={next((g for g in (msg.groups() if msg else []) if g), None)} total={next((g for g in (total.groups() if total else []) if g), None)}")
    if title:
        body = re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", " ", r.text, flags=re.S))
        out.append("   text: " + scrub(re.sub(r"\s+", " ", body))[:300])
    time.sleep(1)


win = {"inqryDiv": 1, "inqryBgnDt": "202610290000", "inqryEndDt": "202610302359", "numOfRows": 3, "pageNo": 1}
show("control bid goods", "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoThng", {**win, "type": "json"})
show("scsbid goods json", "https://apis.data.go.kr/1230000/as/ScsbidInfoService/getScsbidListSttusThng", {**win, "type": "json"})
show("scsbid goods xml", "https://apis.data.go.kr/1230000/as/ScsbidInfoService/getScsbidListSttusThng", win)
show("openg goods json", "https://apis.data.go.kr/1230000/as/ScsbidInfoService/getOpengResultListInfoThng", {**win, "type": "json"})
open("/tmp/probe_out.txt", "w").write("\n".join(out))
