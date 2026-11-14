"""probe 236: 캐나다 CBSA 조사 목록 페이지의 구조 — 사건 머리(나라)와 문서 표(Document·Date issued/updated)가 어떻게 묶이는지. 공개 페이지만, 저장 안 함."""
import html as H
import re

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
OUT = []
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "en,ko;q=0.8"})


def txt(h):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", h or ""))).strip()


try:
    rb = S.get("https://www.cbsa-asfc.gc.ca/robots.txt", timeout=40)
    OUT.append("## robots 전체: " + " | ".join(x.strip() for x in rb.text.splitlines() if x.strip())[:1200])
    r = S.get("https://www.cbsa-asfc.gc.ca/sima-lmsi/i-e/menu-eng.html", timeout=60)
    h = r.text or ""
    main = h[h.find("<main"):h.find("</main>")] if "<main" in h else h
    OUT.append(f"## 목록 {r.status_code} · main {len(main)}자 · details {len(re.findall(r'<details', main))} · summary {len(re.findall(r'<summary', main))} · h3 {len(re.findall(r'<h3', main))} · h4 {len(re.findall(r'<h4', main))} · table {len(re.findall(r'<table', main))} · caption {len(re.findall(r'<caption', main))}")
    tags = re.findall(r"<(details|summary|h2|h3|h4|h5|table|caption|section)\b[^>]*>", main)
    OUT.append("   태그 순서(앞 60): " + " ".join(tags[:60]))
    i = main.lower().find("korea")
    OUT.append(f"   첫 'korea' 위치 {i} · 둘레 HTML(앞 900·뒤 1500): " + re.sub(r"\s+", " ", main[max(0, i - 900):i + 1500])[:2500])
    # 사건 단위로 잘라 보기: table마다 바로 앞 머리 글
    parts = re.split(r"(?=<table)", main)
    OUT.append(f"   table 조각 {len(parts) - 1}")
    kor = 0
    for k in range(1, len(parts)):
        before = parts[k - 1][-1500:]
        heads = re.findall(r"<(summary|h[2-5]|caption|strong|p)\b[^>]*>([\s\S]*?)</\1>", before + parts[k][:600])
        cap = re.findall(r"<caption[^>]*>([\s\S]*?)</caption>", parts[k][:800])
        label = txt(cap[0]) if cap else ""
        prev = [txt(x[1])[:120] for x in heads if txt(x[1])][-3:]
        table = parts[k][:parts[k].find("</table>")]
        rows = re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", table)
        blob = " ".join(prev) + " " + label
        if re.search(r"korea", blob, re.I):
            kor += 1
            if kor <= 5:
                OUT.append(f"   [한국 사건 {kor}] 표 앞 글 {prev} · caption 「{label[:120]}」 · 줄 {len(rows)}")
                for x in rows[:1] + rows[1:4] + rows[-1:]:
                    cells = [txt(c)[:80] for c in re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", x)]
                    OUT.append("       " + " ¦ ".join(cells)[:260] + f" ¦ href {[y[-60:] for y in re.findall(r'href=\"([^\"]+)\"', x)[:1]]}")
    OUT.append(f"   머리·caption에 Korea가 든 표 {kor}개")
    # Korea가 표 밖 어디에 나오는지: 블록 태그별
    for tag in ("summary", "h3", "h4", "h5", "caption", "li", "p", "td", "a", "strong"):
        hits = [txt(x)[:110] for x in re.findall(rf"<{tag}\b[^>]*>([\s\S]*?)</{tag}>", main) if re.search(r"korea", x, re.I)]
        if hits:
            OUT.append(f"   <{tag}>에 Korea {len(hits)}개: " + " | ".join(hits[:4])[:560])
    dates = re.findall(r"<td[^>]*>\s*(20\d{2}-\d{2}-\d{2})\s*</td>", main)
    OUT.append(f"   날짜 칸(yyyy-mm-dd) {len(dates)}개 · 가장 최근 5개 {sorted(dates)[-5:]}")
except Exception as e:  # noqa: BLE001
    OUT.append(f"## CBSA: 실패 {type(e).__name__} {str(e)[:120]}")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines", sum(len(x) for x in OUT), "chars")
