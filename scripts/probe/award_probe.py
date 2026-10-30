"""Probe 11: 오만 Esnad 공개 화면(진행 중·낙찰 목록)의 실제 주소·표 칸 — 공개 자료, 저장하지 않음. 추측 주소는 더 부르지 않는다."""
import re
import time
import requests

out = []
S = requests.Session()
S.headers.update({"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"})
BASE = "https://etendering.tenderboard.gov.om"


def get(url):
    try:
        r = S.get(url, timeout=40)
        out.append(f"\n## {url} -> HTTP {r.status_code} len {len(r.text)}")
        return r.text
    except Exception as e:  # noqa: BLE001
        out.append(f"\n## {url} -> {type(e).__name__} {str(e)[:120]}")
        return ""
    finally:
        time.sleep(1.5)


def func(src, name):
    m = re.search(r"function\s+" + name + r"\s*\([^)]*\)\s*\{(.{0,900}?)\n\s*\}", src, re.S)
    return re.sub(r"\s+", " ", m.group(1))[:600] if m else "(없음)"


def table(t, label):
    body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
    heads = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).strip() for h in re.findall(r"<th[^>]*>(.*?)</th>", body, re.S)]
    out.append(f"[{label}] th: {heads[:30]}")
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S)
    shown = 0
    for row in rows:
        cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len([c for c in cells if c]) >= 4:
            links = re.findall(r"""(?:href|onclick)=['"]([^'"]{4,200})""", row)
            out.append(f"  row: {cells[:12]} links: {links[:4]}")
            shown += 1
            if shown >= 4:
                break
    out.append(f"  rows total {len(rows)} · forms: {re.findall(r'<form[^>]*>', t)[:4]}")
    out.append("  paging/js: " + " | ".join(sorted(set(re.findall(r"(?:pageNo|pageIndex|page=|getPage|goToPage|nextPage|fetch\w*\(|\.action\?[\w=&]*)", t)))[:30]))


home = get(BASE + "/product/publicDash")
for name in ["ViewInProcessTenders", "ViewNewTenders", "getCompletedTenders", "getCanceledTenders", "showOpenData"]:
    out.append(f"{name}: {func(home, name)}")
for flag in ["InProcessTenders", "NewTenders"]:
    t = get(BASE + f"/product/publicDash?viewFlag={flag}")
    table(t, flag)
    for name in ["getTenderDetails", "viewTender", "ViewTenderDetails", "showDetails", "getOpening", "viewBid", "openingDetails"]:
        f = func(t, name)
        if f != "(없음)":
            out.append(f"  {flag} js {name}: {f}")
    out.append("  functions: " + " | ".join(sorted(set(re.findall(r"function\s+(\w+)\s*\(", t)))[:80]))
m = re.search(r"getCompletedTenders\(\)\s*\{[^}]*?['\"](/product/[^'\"]+)['\"]", home, re.S)
if m:
    t = get(BASE + m.group(1))
    table(t, "Completed")
    out.append("  functions: " + " | ".join(sorted(set(re.findall(r"function\s+(\w+)\s*\(", t)))[:80]))
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:400])
