"""probe 194: 개인정보위 위원회 결정문(agenda.do) 첨부 — 피심인·대표자·위반 기간·과징금 꼴, GS리테일 대표이사 변경 공시(2025-03-20). 공개 자료. 저장 안 함."""
import html, os, re, sys, time
import requests

sys.path.insert(0, "scripts")
import official_sanctions as osn  # noqa: E402
import kr_exec_watch as kx  # noqa: E402
import kr_exec_market as km  # noqa: E402

OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


def clean(x):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x or ""))).strip()


s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 (compatible; ReporterRadar/1.0; public records)"})
t0 = time.time()
BASE = "https://www.pipc.go.kr/np/default/agenda.do"
for idx in ("2026-0723", "2026-0689", "2026-0741"):
    v = s.get(BASE, params={"op": "view", "mCode": "E030010000", "idxId": idx}, timeout=30)
    calls = re.findall(r"\w+\(\s*'([^']{6,60})'\s*,\s*'(\d{1,3})'(?:\s*,\s*'(\w{2,5})')?\s*\)", v.text)
    log(f"[{idx}] 첨부 호출 {calls[:4]} · onclick 예 {re.findall(r'on[cC]lick=.{0,120}', v.text)[:2]}")
    body_txt = clean(re.sub(r"<script.*?</script>", " ", v.text, flags=re.S | re.I))
    i = body_txt.find("의결")
    log(f"   본문 글자 일부: {body_txt[max(0, i - 100):i + 300]}")
    for fid, sn, ext in calls[:2]:
        f = s.get(osn.PIPC_FILE.format(fid, sn), headers={"Referer": v.url}, timeout=40)
        txt = osn.attachment_text(f.content) if f.status_code == 200 else None
        log(f"   파일 {fid[:16]} {sn} {ext} HTTP {f.status_code} 머리 {f.content[:4]!r} 크기 {len(f.content)} 글자 {len(txt or '')}")
        if txt:
            t = re.sub(r"\s+", " ", txt)
            log(f"   첫머리: {t[:500]}")
            for w in ("피 심 인", "피심인", "대 표 자", "대표자", "대표이사", "위반기간", "기간", "과 징 금", "과징금", "주 문", "의결연월일", "의결일"):
                for m in list(re.finditer(re.escape(w), t))[:2]:
                    log(f"   {w}: …{t[max(0, m.start() - 30):m.start() + 130]}…")
        time.sleep(0.6)
    time.sleep(0.6)
key = os.environ.get("DART_API_KEY", "")
texts, err = kx.fetch_document(key, "20250320800439", get=s.get, sleep=time.sleep, want=None)
log(f"[GS리테일 대표이사 변경 20250320800439] 원문 {'ok' if texts else err}")
if texts:
    c = km.parse_ceo_change(texts[0])
    log(f"   변경 전 {c.get('before')} · 후 {c.get('after')} · 날짜 {c.get('date')} · 사유 {str(c.get('reason'))[:80]}")
    t = kx.clean(texts[0])
    for w in ("변경전", "변경 전", "변경후", "변경 후", "변경사유", "변경일자", "변경 일자"):
        i = t.find(w)
        if i >= 0:
            log(f"   {w}: {t[i:i + 140]}")
log(f"\n{time.time() - t0:.0f}s")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
