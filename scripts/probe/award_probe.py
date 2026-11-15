"""probe 257: USTR 수집기의 첨부 PDF 읽기가 운영 실행에서 왜 실패하는지(302건 중 239건 '스캔본') — 내려받기 상태·형식·pypdf 오류를 본다."""
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

OUT = []
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pypdf>=4,<7"], check=False)
import pypdf  # noqa: E402
import requests  # noqa: E402
import ustr_comments_watch as w  # noqa: E402

OUT.append(f"pypdf {pypdf.__version__} · requests {requests.__version__}")
KEY = os.environ.get("REGULATIONS_GOV_API_KEY", "").strip() or "DEMO_KEY"
for cid in ["USTR-2026-0498-0147", "USTR-2026-0498-0102", "USTR-2026-0498-0086", "USTR-2026-0498-0146", "USTR-2026-0498-0168", "USTR-2026-0661-0010"]:
    try:
        r = requests.get(f"{w.uc.API}/comments/{cid}", params={"include": "attachments", "api_key": KEY}, headers={"User-Agent": w.UA, "Accept": "application/json"}, timeout=40)
        time.sleep(1.2)
        body = r.json()
        urls = [f["fileUrl"] for inc in body.get("included") or [] for f in (inc.get("attributes") or {}).get("fileFormats") or [] if str(f.get("format")).lower() == "pdf" and f.get("fileUrl")]
        fmts = [str(f.get("format")) for inc in body.get("included") or [] for f in (inc.get("attributes") or {}).get("fileFormats") or []]
        OUT.append(f"{cid}: 상세 HTTP {r.status_code} · 첨부 형식 {fmts} · pdf 주소 {len(urls)}")
        for u in urls[:2]:
            for ua in (w.UA, "Mozilla/5.0 (seoul-reporting-radar probe)"):
                d = requests.get(u, headers={"User-Agent": ua}, timeout=60)
                line = f"   {u[-34:]} · UA '{ua[-12:]}' · HTTP {d.status_code} · {len(d.content)}바이트 · {d.headers.get('content-type')} · 머리 {d.content[:8]!r}"
                try:
                    t, n = w.pdf_text(d.content)
                    line += f" · 글자 {len(t)} · {n}쪽"
                except Exception as e:  # noqa: BLE001
                    line += f" · pdf_text 예외 {type(e).__name__}: {str(e)[:160]} @ {traceback.extract_tb(e.__traceback__)[-1].name}"
                OUT.append(line)
                time.sleep(0.5)
        st = w.read_comment(cid, KEY, get=requests.get, sleep=time.sleep, budget=w.uc.Budget(5))
        OUT.append(f"   read_comment → 상태 {st[0]} · 글자 {len(st[1])} · {st[2]}쪽 · 첨부 {st[3]} · 오류 {st[4]}")
    except Exception as e:  # noqa: BLE001
        OUT.append(f"{cid}: 예외 {type(e).__name__}: {str(e)[:200]}")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
