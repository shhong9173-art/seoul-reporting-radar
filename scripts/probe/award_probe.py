"""probe 109: 출입처 외신 검색(구글 뉴스 RSS)에서 '매체 허용 목록 밖'으로 버린 매체 분포 — 석유화학·정유·에너지화학·철강·전력(매체 이름·건수·7일 안 건수만)."""
import collections, re, sys, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import requests
import ast, types
src = open("global_collector.py", encoding="utf-8").read()
tree = ast.parse(src)
keep = [n for n in tree.body if isinstance(n, ast.Assign) and any(getattr(t, "id", "") in ("QUERIES", "FOREIGN_OK", "DOMESTIC_EN") for t in n.targets)]
keep += [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "looks_korean"]
ns = {"re": re}
exec(compile(ast.Module(body=keep, type_ignores=[]), "gc", "exec"), ns)
g = types.SimpleNamespace(**ns)
OUT = []
def p(*a):
    OUT.append(" ".join(str(x) for x in a))
now = datetime.now(timezone.utc)
for cat, q in g.QUERIES if hasattr(g, "QUERIES") else []:
    pass
queries = [(c, q) for c, q in getattr(g, "SOURCES", getattr(g, "QUERIES", [])) if c.startswith("출입처")]
p("queries", [c for c, _ in queries])
for cat, q in queries:
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(q) + "&hl=en-US&gl=US&ceid=US:en"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 AutoIndustryGlobalRadar/1.1"}, timeout=30)
    root = ET.fromstring(r.content)
    outlet, recent = collections.Counter(), collections.Counter()
    for it in root.findall("./channel/item"):
        src = it.find("source")
        s = (src.text or "").strip() if src is not None else "?"
        title = it.findtext("title") or ""
        if g.DOMESTIC_EN.search(s) or g.looks_korean(title) or g.looks_korean(s) or g.FOREIGN_OK.search(s):
            continue
        outlet[s] += 1
        try:
            if parsedate_to_datetime(it.findtext("pubDate") or "") > now - timedelta(days=7):
                recent[s] += 1
        except Exception:
            pass
    p(f"== {cat}: 허용 밖 {sum(outlet.values())} · 7일 안 {sum(recent.values())}")
    p("   " + ", ".join(f"{k} {v}({recent.get(k, 0)})" for k, v in outlet.most_common(25)))
text = "\n".join(OUT)
open("/tmp/probe_out.txt", "w").write(text)
print(text[:800])
