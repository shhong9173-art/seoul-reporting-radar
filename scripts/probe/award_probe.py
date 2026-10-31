"""Probe 31: 고용24 OPEN-API 채용정보·공통코드 — 호출 주소·응답 형식·출입처 키워드 검색 건수만. 키·공고 제목·회사명은 출력하지 않는다."""
import collections
import os
import re
import time
import xml.etree.ElementTree as ET
import requests

out = []
RK = os.environ.get("WORK24_RECRUIT_KEY", "").strip()
CK = os.environ.get("WORK24_CODE_KEY", "").strip()
out.append(f"keys set: recruit={bool(RK)} len={len(RK)} code={bool(CK)} len={len(CK)}")
B = "https://www.work24.go.kr/cm/openApi/call/wk/"
H = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}


def scrub(t):
    return re.sub(r"[A-Za-z0-9\-]{20,}", "<redacted>", t)


def call(name, params):
    try:
        r = requests.get(B + name, params=params, headers=H, timeout=30)
        return r
    except Exception as e:  # noqa: BLE001
        out.append(f"{name}: {type(e).__name__} {scrub(str(e))[:120]}")
        return None


def tags(el):
    return [c.tag for c in el]


# 1) 목록: 키워드 없이 1쪽
r = call("callOpenApiSvcInfo210L01.do", {"authKey": RK, "callTp": "L", "returnType": "XML", "startPage": 1, "display": 10})
if r is not None:
    out.append(f"list plain: HTTP {r.status_code} ctype={r.headers.get('content-type')} len={len(r.text)} head={scrub(r.text[:160])!r}")
    try:
        root = ET.fromstring(r.content)
        out.append(f"   root={root.tag} children={tags(root)[:8]} total={root.findtext('total')}")
        w = root.find("wanted")
        if w is not None:
            out.append(f"   wanted tags={tags(w)}")
            out.append(f"   regDt sample format={re.sub(r'[0-9]', '9', w.findtext('regDt') or '')} closeDt={re.sub(r'[0-9]', '9', w.findtext('closeDt') or '')}")
    except ET.ParseError as e:
        out.append(f"   parse error {e}")
time.sleep(1)
# 2) 출입처 키워드 검색 건수
first_id = None
for kw in ("현대자동차", "기아", "현대모비스", "현대제철", "포스코", "고려아연", "LS일렉트릭", "LS전선", "한화솔루션", "두산에너빌리티", "HD현대일렉트릭", "한국타이어"):
    r = call("callOpenApiSvcInfo210L01.do", {"authKey": RK, "callTp": "L", "returnType": "XML", "startPage": 1, "display": 100, "keyword": kw})
    if r is None:
        continue
    try:
        root = ET.fromstring(r.content)
        ws = root.findall("wanted")
        comp_hit = sum(1 for w in ws if kw.replace("현대자동차", "현대자동차") in (w.findtext("company") or ""))
        title_hit = sum(1 for w in ws if kw in (w.findtext("title") or ""))
        bus = len({w.findtext("busino") for w in ws if kw in (w.findtext("company") or "")})
        regs = sorted(w.findtext("regDt") or "" for w in ws)
        out.append(f"kw#{kw[:2]}..: HTTP {r.status_code} total={root.findtext('total')} got={len(ws)} company-hit={comp_hit} title-hit={title_hit} distinct-busino-of-hits={bus} reg {regs[:1]}..{regs[-1:]}")
        if first_id is None and ws:
            first_id = ws[0].findtext("wantedAuthNo")
    except ET.ParseError:
        out.append(f"kw#{kw[:2]}..: HTTP {r.status_code} non-XML head={scrub(r.text[:120])!r}")
    time.sleep(1)
# 3) 상세 후보
if first_id:
    for name in ("callOpenApiSvcInfo210D01.do",):
        r = call(name, {"authKey": RK, "callTp": "D", "returnType": "XML", "wantedAuthNo": first_id, "infoSvc": "VALIDATION"})
        if r is not None:
            out.append(f"detail {name}: HTTP {r.status_code} len={len(r.text)} head-tags={re.findall(r'<([A-Za-z]+)>', r.text)[:40]}")
# 4) 공통코드 후보
for name, params in (("callOpenApiSvcInfo21L01.do", {"target": "CMCD", "dtlGb": 1}),
                     ("callOpenApiSvcInfo210L21.do", {"target": "CMCD", "dtlGb": 1}),
                     ("callOpenApiSvcInfo2CL01.do", {"target": "CMCD", "dtlGb": 1})):
    r = call(name, {"authKey": CK, "returnType": "XML", **params})
    if r is not None:
        out.append(f"code {name}: HTTP {r.status_code} len={len(r.text)} head={scrub(r.text[:200])!r}")
    time.sleep(1)
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:300])
