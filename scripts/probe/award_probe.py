"""probe 224: 223에서 열린 원천의 속 구조(목록 요청 주소·표 꼴)를 본다. 공개 페이지만, 저장 안 함."""
import io
import re

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
OUT = []
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "ko,en;q=0.8"})


def text_of(html):
    t = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", html or "", flags=re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t)).strip()


def get(label, url, enc=None, method="GET", data=None, headers=None, timeout=40):
    try:
        r = S.request(method, url, data=data, headers=headers, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        OUT.append(f"## {label}: 실패 {type(e).__name__} {str(e)[:80]}")
        return None, ""
    if enc:
        r.encoding = enc
    OUT.append(f"## {label}: {r.status_code} {len(r.content)}바이트 ct={r.headers.get('content-type', '')[:40]}")
    return r, r.text or ""


def rows_of(html, n=4, cut=70):
    rows = re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", html, re.I)
    OUT.append(f"   표 줄 {len(rows)}")
    for row in rows[:n]:
        OUT.append("   행: " + " ¦ ".join(text_of(c)[:cut] for c in re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", row, re.I)))


def urls_in(html, pat, n=14):
    found = list(dict.fromkeys(re.findall(pat, html)))
    OUT.append(f"   주소({len(found)}): " + " | ".join(x[:80] for x in found[:n]))


# 1. TRA: 목록의 한국 줄, 제출 문서 PDF 읽기
r, h = get("TRA 목록", "https://public-file.trade-remedies.service.gov.uk/", enc="utf-8")
for row in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", h):
    if "Korea" in row:
        OUT.append("   한국 줄: " + " ¦ ".join(text_of(c)[:50] for c in re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", row)) + " ¦ " + " ".join(re.findall(r'href="([^"]*case/[^"]+)"', row))[:120])
r, h = get("TRA ad0071", "https://public-file.trade-remedies.service.gov.uk/case/ad0071", enc="utf-8")
rows = re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", h)
OUT.append(f"   줄 {len(rows)} · 당사자: " + " / ".join(sorted({text_of(re.findall(r'<t[dh][^>]*>([\s\S]*?)</t[dh]>', x)[1])[7:60] for x in rows[1:] if len(re.findall(r'<t[dh]', x)) > 2}))[:700])
m = re.search(r'<tr[^>]*>([\s\S]*?)</tr>', h[h.find("<tbody"):] if "<tbody" in h else h)
OUT.append("   첫 행 원문: " + re.sub(r"\s+", " ", (m.group(1) if m else ""))[:500])
r, h = get("TRA 제출 1239", "https://public-file.trade-remedies.service.gov.uk/case/ad0092/submission/1239", enc="utf-8")
pdfs = re.findall(r'href="(https://[^"]+azurefd\.net/[^"]+)"', h)
OUT.append("   파일: " + " | ".join(p[-90:] for p in pdfs[:4]))
OUT.append("   글: " + text_of(h)[330:900])
if pdfs:
    try:
        pr = S.get(pdfs[0], timeout=60)
        OUT.append(f"   PDF {pr.status_code} {len(pr.content)}바이트 머리 {pr.content[:5]!r}")
        from pypdf import PdfReader
        rd = PdfReader(io.BytesIO(pr.content))
        t = re.sub(r"\s+", " ", " ".join((p.extract_text() or "") for p in rd.pages[:3]))
        OUT.append(f"   PDF {len(rd.pages)}쪽 글자 {len(t)} · LG {len(re.findall('LG Chem', t))} · Hanwha {len(re.findall('Hanwha', t))} · 앞: {t[:260]}")
    except Exception as e:  # noqa: BLE001
        OUT.append(f"   PDF 실패 {type(e).__name__} {str(e)[:80]}")
# 2. ev.or.kr
r, h = get("ev.or.kr 지급대상", "https://ev.or.kr/nportal/buySupprt/initSubsidyTargetVehicleAction.do", enc="utf-8")
OUT.append("   앞 원문: " + re.sub(r"\s+", " ", h[:300]))
urls_in(h, r"['\"](/nportal/[A-Za-z0-9_/]+\.do)['\"]")
OUT.append("   낱말: " + " ".join(f"{w}={h.count(w)}" for w in ("아이오닉", "차종", "국비", "모델명", "<table", "<li", "제조사")))
i = h.find("아이오닉")
OUT.append("   아이오닉 둘레: " + re.sub(r"\s+", " ", h[max(0, i - 300):i + 300]) if i >= 0 else "   아이오닉 없음")
# 3. car.go.kr
for label, u in (("리콜현황", "https://www.car.go.kr/ri/stat/list.do"), ("무상점검", "https://www.car.go.kr/ri/grts/list.do")):
    r, h = get(f"car.go.kr {label}", u, enc="utf-8")
    urls_in(h, r"['\"](/[A-Za-z0-9_/]+\.(?:do|json))['\"]", n=20)
    urls_in(h, r"url\s*:\s*['\"]([^'\"]+)['\"]", n=10)
# 4. 전파연구원 새 목록
r, h = get("RRA 신규 목록", "https://www.rra.go.kr/ko/license/A_b_newlist.do", enc="euc-kr")
OUT.append("   글: " + text_of(h)[600:900])
rows_of(h, n=5)
r, h = get("RRA 검색", "https://www.rra.go.kr/ko/license/A_c_search.do", enc="euc-kr")
OUT.append("   폼: " + " | ".join(re.findall(r'<(?:input|select)[^>]*name="([^"]+)"', h)[:30]))
rows_of(h, n=3)
# 5. 통합환경허가 메뉴
r, h = get("통합환경허가", "https://ieps.nier.go.kr/web/main", enc="utf-8")
menu = re.findall(r'<a[^>]*href="([^"]+)"[^>]*>([^<]{2,30})</a>', h)
OUT.append("   메뉴: " + " | ".join(f"{t.strip()}={u[:60]}" for u, t in menu if re.search(r"공개|허가|사업장|검토|현황", t))[:900])
# 6. CARB · vPIC · 호주
r, h = get("CARB 승용 EO", "https://ww2.arb.ca.gov/applications/new-vehicle-and-engine-certification-executive-orders-light-duty-vehicles", enc="utf-8")
OUT.append("   글: " + text_of(h)[300:700])
urls_in(h, r'href="([^"]*(?:eo|cert|onroad|msprog)[^"]*)"', n=10)
r, h = get("vPIC MID 복제", "https://vpic.nhtsa.dot.gov/mid/Replica/Index", enc="utf-8")
OUT.append("   글: " + text_of(h)[200:600])
urls_in(h, r"['\"](/mid/[A-Za-z0-9_/?=&]+)['\"]", n=12)
r, h = get("호주 ADC", "https://www.industry.gov.au/anti-dumping-commission/current-cases-and-electronic-public-record-epr", timeout=90)
OUT.append("   Korea " + str(h.count("Korea")) + " · 글: " + text_of(h)[400:700])
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
