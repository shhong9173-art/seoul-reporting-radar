"""Probe 32: 국가법령정보 OPEN API(DRF) — 승인·IP 검증 여부, 행정규칙·법령·해석례 목록 형식과 규모. OC 값·본문은 출력하지 않는다(건수·태그·부처명만)."""
import collections
import os
import re
import time
import xml.etree.ElementTree as ET
import requests

out = []
OC = os.environ.get("LAW_OC", "").strip()
out.append(f"LAW_OC set={bool(OC)} len={len(OC)} ascii={OC.isascii()}")
B = "https://www.law.go.kr/DRF/"
H = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}


def scrub(t):
    return t.replace(OC, "<OC>") if OC else t


def get(path, **params):
    try:
        r = requests.get(B + path, params={"OC": OC, "type": "XML", **params}, headers=H, timeout=40)
    except Exception as e:  # noqa: BLE001
        out.append(f"{path} {params}: {type(e).__name__} {scrub(str(e))[:120]}")
        return None, None
    try:
        return r, ET.fromstring(r.content)
    except ET.ParseError:
        out.append(f"{path} {params.get('target')}: HTTP {r.status_code} non-XML ctype={r.headers.get('content-type')} head={scrub(r.text[:200])!r}")
        return r, None


def items(root):
    return [c for c in root if len(c)]


r, root = get("lawSearch.do", target="law", query="전기사업법")
if root is not None:
    out.append(f"law search: HTTP {r.status_code} root={root.tag} totalCnt={root.findtext('totalCnt')} top-tags={[c.tag for c in root][:8]}")
    it = items(root)
    if it:
        out.append(f"   item tags={[c.tag for c in it[0]]}")
time.sleep(1)
r, root = get("lawSearch.do", target="admrul", query="자동차", display=20, sort="ddes")
first = None
if root is not None:
    it = items(root)
    out.append(f"admrul q=자동차: HTTP {r.status_code} root={root.tag} totalCnt={root.findtext('totalCnt')} n={len(it)}")
    if it:
        out.append(f"   item tags={[c.tag for c in it[0]]}")
        dates = sorted(x.findtext('발령일자') or '' for x in it)
        out.append(f"   발령일자 range {dates[:1]}..{dates[-1:]}; 종류 {dict(collections.Counter(x.findtext('행정규칙종류') for x in it))}")
        first = it[0].findtext("행정규칙일련번호")
time.sleep(1)
for rng in ("20261001~20261031", "20261024~20261031"):
    r, root = get("lawSearch.do", target="admrul", prmlYd=rng, display=100, sort="ddes")
    if root is not None:
        it = items(root)
        orgs = collections.Counter(x.findtext("소관부처명") for x in it)
        out.append(f"admrul 발령 {rng}: HTTP {r.status_code} totalCnt={root.findtext('totalCnt')} page1={len(it)} 부처 top={orgs.most_common(12)}")
        out.append(f"   제개정 {dict(collections.Counter(x.findtext('제개정구분명') for x in it))} 종류 {dict(collections.Counter(x.findtext('행정규칙종류') for x in it))}")
    time.sleep(1)
r, root = get("lawSearch.do", target="law", efYd="20261101~20261231", display=100)
if root is not None:
    out.append(f"law 시행 11~12월: HTTP {r.status_code} totalCnt={root.findtext('totalCnt')}")
time.sleep(1)
for tgt in ("expc", "motieCgmExpc", "meCgmExpc", "molitCgmExpc", "kcsCgmExpc", "mcmExpc"):
    r, root = get("lawSearch.do", target=tgt, query="전기", display=5)
    if root is not None:
        out.append(f"target={tgt}: HTTP {r.status_code} root={root.tag} totalCnt={root.findtext('totalCnt')} text={scrub((root.text or '').strip())[:80]!r} first-tags={[c.tag for c in (items(root) or [root])[0]][:12]}")
    time.sleep(1)
if first:
    r, root = get("lawService.do", target="admrul", ID=first)
    if root is not None:
        out.append(f"admrul body: HTTP {r.status_code} root={root.tag} tags={[c.tag for c in root][:20]} len={len(r.text)}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:300])
