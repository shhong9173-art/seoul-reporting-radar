"""Probe 12: 오만 Esnad 개찰 현황 공개 보고서(showOpeningStatus_public)·낙찰 목록(CompletedTendersForPublic, 화면 양식 그대로 POST) — 공개 자료, 저장하지 않음."""
import html
import re
import time
import requests

out = []
S = requests.Session()
S.headers.update({"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"})
BASE = "https://etendering.tenderboard.gov.om"


def req(method, url, **kw):
    try:
        r = S.request(method, url, timeout=40, **kw)
        out.append(f"\n## {method} {url} -> HTTP {r.status_code} len {len(r.text)}")
        return r.text
    except Exception as e:  # noqa: BLE001
        out.append(f"\n## {method} {url} -> {type(e).__name__} {str(e)[:120]}")
        return ""
    finally:
        time.sleep(1.5)


def func(src, name):
    m = re.search(r"function\s+" + name + r"\s*\([^)]*\)\s*\{(.{0,1500}?)\n\s*\}", src, re.S)
    return re.sub(r"\s+", " ", m.group(0))[:1200] if m else "(없음)"


def text(t, n):
    body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " | ", body)))[:n]


def hidden(t, form):
    m = re.search(r'<form[^>]*name="' + form + r'".*?</form>', t, re.S)
    f = m.group(0) if m else t
    return {a: b for a, b in re.findall(r"""<input[^>]*type=['"]hidden['"][^>]*name=['"]([^'"]+)['"][^>]*value=['"]([^'"]*)['"]""", f)}


ip = req("GET", BASE + "/product/publicDash?viewFlag=InProcessTenders")
for name in ["showOpeningStatus_Report", "showParticipated", "getNit", "ShowPage", "submitPage", "formSubmit"]:
    out.append(f"{name}: {func(ip, name)}")
calls = re.findall(r"showOpeningStatus_Report\(([^)]*)\)", ip)
out.append(f"opening calls {len(calls)}: {calls[:4]}")
out.append(f"participated calls: {re.findall(r'showParticipated[(]([^)]*)[)]', ip)[:3]}")
out.append(f"hidden fields: {list(hidden(ip, 'bDashboard').items())[:30]}")
m = re.search(r"['\"](/product/[^'\"]*callAction=showOpeningStatus_public[^'\"]*)['\"]", ip)
out.append(f"opening url pattern: {m.group(1) if m else None}")
# 개찰 보고서: 화면 함수가 여는 주소 그대로 처음 2건
for c in calls[:2]:
    args = [a.strip().strip("'\"") for a in c.split(",")]
    if m:
        url = BASE + m.group(1) + (args[0] if args else "")
        t = req("GET", url)
        out.append(text(t, 2500))
# 낙찰 목록: 대시보드 양식 그대로 POST
home = req("GET", BASE + "/product/publicDash")
fields = hidden(home, "bDashboard")
t = req("POST", BASE + "/product/CompletedTendersForPublic", data=fields, headers={"Referer": BASE + "/product/publicDash"})
out.append(text(t, 3000))
out.append("links: " + " | ".join(sorted(set(re.findall(r"""(?:href|onclick)=['"]([^'"]{4,200})""", t)))[:20]))
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:400])
