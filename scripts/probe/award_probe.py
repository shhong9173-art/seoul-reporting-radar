"""probe 237: 캐나다 CBSA — 조사 목록 말고 재조사·정상가격 재심, 종료재심, 시행 중 조치 목록이 같은 꼴인지(한국 사건 수·가장 최근 문서일). 공개 페이지만, 저장 안 함."""
import html as H
import re
import time
from urllib.parse import urljoin

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
OUT = []
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "en,ko;q=0.8"})
BASE = "https://www.cbsa-asfc.gc.ca/sima-lmsi/i-e/menu-eng.html"


def txt(h):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", h or ""))).strip()


def cases(main):
    out = []
    for m in re.finditer(r"<details\b[^>]*>([\s\S]*?)</details>", main):
        block = m.group(1)
        s = re.search(r"<summary[^>]*>([\s\S]*?)</summary>", block)
        title = txt(s.group(1)) if s else ""
        docs = []
        for row in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", block):
            tds = re.findall(r"<td[^>]*>([\s\S]*?)</td>", row)
            if len(tds) < 2:
                continue
            d = re.search(r'datetime="(\d{4}-\d{2}-\d{2})"', tds[-1]) or re.search(r"(\d{4}-\d{2}-\d{2})", tds[-1])
            docs.append((txt(tds[0])[:90], d.group(1) if d else txt(tds[-1])[:20]))
        out.append((title, docs))
    return out


try:
    r = S.get(BASE, timeout=60)
    h = r.text or ""
    main = h[h.find("<main"):h.find("</main>")]
    links = [(txt(t)[:60], urljoin(BASE, u)) for u, t in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', h) if "/sima-lmsi/" in u and "menu" in u]
    seen = {}
    for t, u in links:
        seen.setdefault(u, t)
    OUT.append("## 조사 목록에서 걸린 다른 목록 링크: " + " | ".join(f"{t} → {u[30:]}" for u, t in seen.items())[:1500])
    h3 = [txt(x)[:50] for x in re.findall(r"<h3[^>]*>([\s\S]*?)</h3>", main)]
    OUT.append(f"   h3 {len(h3)}개: {h3[:12]}")
    cs = cases(main)
    kor = [(t, d) for t, d in cs if re.search(r"korea", t, re.I)]
    OUT.append(f"   조사 목록 사건 {len(cs)} · 한국 {len(kor)} · 한국 사건 문서 줄 {sum(len(d) for _, d in kor)} · 날짜 못 읽은 줄 {sum(1 for _, d in kor for x in d if not re.match(r'20\d\d-', x[1]))}")
    latest = sorted(((x[1], t[:60], x[0]) for t, d in kor for x in d if re.match(r"20\d\d-", x[1])), reverse=True)[:6]
    OUT.append("   한국 사건 가장 최근 문서: " + " | ".join(f"{a} {b} 「{c}」" for a, b, c in latest)[:1100])
    inprog = [t[:90] for t, d in cs if not re.search(r"conclud|terminat", t, re.I)]
    OUT.append(f"   '종결' 낱말 없는 사건 {len(inprog)}: {inprog[:8]}")
    for name, u in (("재조사·정상가격 재심", "https://www.cbsa-asfc.gc.ca/sima-lmsi/ri-re/menu-eng.html"), ("종료재심", "https://www.cbsa-asfc.gc.ca/sima-lmsi/er-rre/menu-eng.html"),
                    ("시행 중 조치", "https://www.cbsa-asfc.gc.ca/sima-lmsi/mif-mev/menu-eng.html")):
        time.sleep(2)
        try:
            p = S.get(u, timeout=60)
            ph = p.text or ""
            pm = ph[ph.find("<main"):ph.find("</main>")] if "<main" in ph else ph
            pc = cases(pm)
            pk = [(t, d) for t, d in pc if re.search(r"korea", t, re.I)]
            OUT.append(f"## {name} {p.status_code} · main {len(pm)}자 · details {len(pc)} · table {len(re.findall(r'<table', pm))} · 머리에 Korea {len(pk)} · 본문 Korea {len(re.findall(r'korea', pm, re.I))} · h1 {[txt(x)[:60] for x in re.findall(r'<h1[^>]*>([\s\S]*?)</h1>', pm)][:1]}")
            OUT.append("   머리 앞 5개: " + " | ".join(t[:100] for t, _ in pc[:5])[:700])
            OUT.append("   한국 머리 앞 5개: " + " | ".join(f"{t[:100]} (문서 {len(d)})" for t, d in pk[:5])[:800])
            lat = sorted(((x[1], t[:50], x[0]) for t, d in pc for x in d if re.match(r"20\d\d-", x[1]) and (re.search(r"korea", t, re.I) or re.search(r"korea|hyundai|posco|seah|husteel|nexteel|dongkuk|kg steel|hyosung|ls ", x[0], re.I))), reverse=True)[:8]
            OUT.append("   한국 관련 가장 최근 문서: " + " | ".join(f"{a} {b} 「{c}」" for a, b, c in lat)[:1300])
            i = pm.lower().find("korea")
            OUT.append("   첫 Korea 둘레: " + re.sub(r"\s+", " ", pm[max(0, i - 500):i + 700])[:1200] if i >= 0 else "   Korea 없음")
        except Exception as e:  # noqa: BLE001
            OUT.append(f"## {name}: 실패 {type(e).__name__} {str(e)[:80]}")
except Exception as e:  # noqa: BLE001
    OUT.append(f"## CBSA: 실패 {type(e).__name__} {str(e)[:120]}")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines", sum(len(x) for x in OUT), "chars")
