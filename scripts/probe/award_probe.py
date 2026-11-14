"""probe 238: 캐나다 CBSA — '옮김'이라고 나온 재조사 목록이 어디로 갔는지, 시행 중 조치 사건 페이지(mif-mev)의 꼴(재조사·정상가격 재심·업체 이름이 어디에). 공개 페이지만."""
import html as H
import re
import time
from urllib.parse import urljoin

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


try:
    st, m = main_of("https://www.cbsa-asfc.gc.ca/sima-lmsi/ri-re/menu-eng.html")
    OUT.append(f"## 재조사 목록(옮김) {st}: {txt(m)[:500]} · 링크 {[(txt(t)[:40], u) for u, t in re.findall(r'<a[^>]+href=\"([^\"]+)\"[^>]*>([\s\S]*?)</a>', m)][:6]}")
    time.sleep(2)
    base = "https://www.cbsa-asfc.gc.ca/sima-lmsi/mif-mev/menu-eng.html"
    st, m = main_of(base)
    rows = re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", m)
    ths = [txt(x)[:30] for x in re.findall(r"<th[^>]*>([\s\S]*?)</th>", m)]
    kor = []
    for x in rows:
        tds = re.findall(r"<td[^>]*>([\s\S]*?)</td>", x)
        if len(tds) >= 4 and re.search(r"korea", txt(tds[3]), re.I):
            href = re.findall(r'href="([^"]+)"', x)
            kor.append((txt(tds[0]), txt(tds[1])[:50], txt(tds[2]), urljoin(base, href[0]) if href else ""))
    OUT.append(f"## 시행 중 조치 {st} · 줄 {len(rows)} · 표 머리 {ths[:8]} · 한국 줄 {len(kor)}: " + " | ".join(f"{a} {b} {c}" for a, b, c, _ in kor)[:1200])
    for code, name, kind, u in kor[:2] + [k for k in kor if re.search(r"transformer|OCTG|oil country", k[1], re.I)][:1]:
        time.sleep(2)
        st, pm = main_of(u)
        OUT.append(f"## 조치 페이지 {code} 「{name}」 {st} · {len(pm)}자 · h2 {[txt(x)[:40] for x in re.findall(r'<h2[^>]*>([\s\S]*?)</h2>', pm)][:12]} · h3 {[txt(x)[:40] for x in re.findall(r'<h3[^>]*>([\s\S]*?)</h3>', pm)][:14]}")
        OUT.append(f"   details {len(re.findall(r'<details', pm))} · summary {[txt(x)[:60] for x in re.findall(r'<summary[^>]*>([\s\S]*?)</summary>', pm)][:14]}")
        OUT.append(f"   table {len(re.findall(r'<table', pm))} · 표 머리 {[txt(x)[:28] for x in re.findall(r'<th[^>]*>([\s\S]*?)</th>', pm)][:14]}")
        dated = []
        for x in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", pm):
            tds = re.findall(r"<td[^>]*>([\s\S]*?)</td>", x)
            d = re.search(r'datetime="(\d{4}-\d{2}-\d{2})"', x) or re.search(r"(20\d{2}-\d{2}-\d{2})", txt(x))
            if tds and d:
                dated.append((d.group(1), " ¦ ".join(txt(t)[:70] for t in tds)[:200]))
        dated.sort(reverse=True)
        OUT.append(f"   날짜 든 표 줄 {len(dated)} · 최근 8: " + " | ".join(f"{a} {b}" for a, b in dated[:8])[:1500])
        lis = [txt(x)[:140] for x in re.findall(r"<li[^>]*>([\s\S]*?)</li>", pm) if re.search(r"20\d{2}", x) and re.search(r"review|re-investigation|normal value|expiry|notice|conclu", x, re.I)]
        OUT.append(f"   날짜·절차 낱말 든 li {len(lis)} · 앞 8: " + " | ".join(lis[:8])[:1300])
        names = sorted(set(re.findall(r"\b(?:Hyundai[A-Za-z &.]{0,30}|HD Hyundai[A-Za-z &.]{0,20}|Hyosung[A-Za-z &.]{0,30}|LS Electric[A-Za-z &.]{0,10}|Iljin[A-Za-z &.]{0,20}|POSCO[A-Za-z &.]{0,20}|SeAH[A-Za-z &.]{0,20}|Husteel|Nexteel[A-Za-z &.]{0,10}|Dongkuk[A-Za-z &.]{0,20}|KG [A-Za-z]{3,12})", txt(pm))))
        OUT.append(f"   출입처 꼴 이름 {names[:16]}")
except Exception as e:  # noqa: BLE001
    OUT.append(f"## CBSA: 실패 {type(e).__name__} {str(e)[:120]}")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines", sum(len(x) for x in OUT), "chars")
