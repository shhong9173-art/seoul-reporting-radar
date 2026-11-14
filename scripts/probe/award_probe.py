"""probe 239: 캐나다 CBSA — 행정재심 목록(ar-ra)의 꼴, 시행 중 조치 사건 페이지(TR·SPT)의 '조사 정보' 표와 수출자 표 HTML. 공개 페이지만."""
import html as H
import re
import time

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
OUT = []
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "en,ko;q=0.8"})


def txt(h):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", h or ""))).strip()


def main_of(u):
    r = S.get(u, timeout=60)
    h = r.text or ""
    return r.status_code, (h[h.find("<main"):h.find("</main>")] if "<main" in h else h)


def squeeze(h):
    return re.sub(r"\s+", " ", h)


try:
    st, m = main_of("https://www.cbsa-asfc.gc.ca/sima-lmsi/ar-ra/menu-eng.html")
    det = re.findall(r"<details\b[^>]*>([\s\S]*?)</details>", m)
    heads = [txt(re.search(r"<summary[^>]*>([\s\S]*?)</summary>", d).group(1)) if re.search(r"<summary", d) else "" for d in det]
    OUT.append(f"## 행정재심 목록 {st} · main {len(m)}자 · h1 {[txt(x)[:60] for x in re.findall(r'<h1[^>]*>([\s\S]*?)</h1>', m)][:1]} · details {len(det)} · table {len(re.findall(r'<table', m))} · h3 {[txt(x)[:24] for x in re.findall(r'<h3[^>]*>([\s\S]*?)</h3>', m)][:8]}")
    kor = [(h, d) for h, d in zip(heads, det) if re.search(r"korea", h + d, re.I)]
    OUT.append(f"   머리 앞 6: " + " | ".join(x[:110] for x in heads[:6])[:800])
    OUT.append(f"   Korea 든 사건(머리나 표 안) {len(kor)} · 머리에만 {sum(1 for h in heads if re.search(r'korea', h, re.I))}")
    for h, d in kor[:6]:
        rows = []
        for x in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", d):
            tds = re.findall(r"<td[^>]*>([\s\S]*?)</td>", x)
            dd = re.search(r'datetime="(\d{4}-\d{2}-\d{2})"', x)
            if tds:
                rows.append(f"{dd.group(1) if dd else txt(tds[-1])[:12]} {txt(tds[0])[:70]}")
        OUT.append(f"   · {h[:150]} — 문서 {len(rows)}: " + " | ".join(rows[:5])[:520])
    i = m.lower().find("korea")
    OUT.append("   첫 Korea 둘레 HTML: " + squeeze(m[max(0, i - 700):i + 900])[:1600])
    for code in ("tr", "spt"):
        time.sleep(2)
        st, pm = main_of(f"https://www.cbsa-asfc.gc.ca/sima-lmsi/mif-mev/{code}-eng.html")
        OUT.append(f"## 조치 페이지 {code} {st} · {len(pm)}자 · dateModified {re.findall(r'dateModified[^<]{0,60}<[^>]*>[^<]{0,20}', pm)[:1]}")
        a = pm.find("Investigation information")
        a = a if a >= 0 else pm.find("Investigations Information")
        OUT.append("   '조사 정보' 둘레 HTML: " + squeeze(pm[a:a + 2600])[:2600])
        b = pm.find("Disclosure of normal values")
        b = b if b >= 0 else pm.find("Disclosure of Normal Values")
        seg = pm[b:b + 6000] if b >= 0 else ""
        tb = seg.find("<table")
        OUT.append("   수출자 표 HTML 앞부분: " + squeeze(seg[tb:tb + 1900])[:1900])
        rows = []
        for x in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", seg):
            tds = [txt(t)[:60] for t in re.findall(r"<td[^>]*>([\s\S]*?)</td>", x)]
            if tds:
                rows.append(" ¦ ".join(tds))
        OUT.append(f"   수출자 표 줄 {len(rows)}: " + " | ".join(rows[:14])[:1500])
        h3 = [txt(x)[:70] for x in re.findall(r"<h3[^>]*>([\s\S]*?)</h3>", pm)]
        OUT.append(f"   h3 {h3[:8]}")
        c = pm.find("Duty liability")
        OUT.append("   세율 대목 글: " + txt(pm[c:c + 2500])[:900])
except Exception as e:  # noqa: BLE001
    OUT.append(f"## CBSA: 실패 {type(e).__name__} {str(e)[:120]}")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines", sum(len(x) for x in OUT), "chars")
