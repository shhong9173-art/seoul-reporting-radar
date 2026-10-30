"""Probe 14: Nama iSupplier(Oracle) 입찰 공고 화면(OETC·NSS) — 해외 IP에서 열리는지, 공개 칸(마감·개찰·낙찰). 공개 자료, 저장하지 않음."""
import html
import re
import time
import requests

out = []
S = requests.Session()
S.headers.update({"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"})
for f in ["XXTEN_TENDER_FLOAT_OETC_F", "XXTEN_TENDER_FLOAT_NSS_F"]:
    url = f"https://isupplier.nama.om:4443/OA_HTML/OA.jsp?OAFunc={f}"
    try:
        r = S.get(url, timeout=40)
        body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", r.text, flags=re.S)
        txt = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " | ", body)))
        out.append(f"\n## {f} -> HTTP {r.status_code} len {len(r.text)} final {r.url}\n{txt[:2500]}")
        out.append("links: " + " | ".join(sorted(set(re.findall(r"""href=['"]([^'"]{6,200})""", r.text)))[:25]))
        out.append("OAFunc refs: " + " | ".join(sorted(set(re.findall(r"OAFunc=([A-Z0-9_]+)", r.text)))[:25]))
    except Exception as e:  # noqa: BLE001
        out.append(f"\n## {f} -> {type(e).__name__} {str(e)[:200]}")
    time.sleep(2)
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:400])
