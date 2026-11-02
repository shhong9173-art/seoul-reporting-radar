"""probe 103: 새올 공고 상세의 첨부 파일 내려받기 경로(울주 68156 고려아연 #2ASU) — 링크 모양, hwpx 본문 글자, pdf 글자 수."""
import io, re, zipfile
import requests
OUT = []
def p(*a):
    OUT.append(" ".join(str(x) for x in a))
UA = {"User-Agent": "Mozilla/5.0 (research; seoul-reporting-radar)"}
url = ("http://eminwon.ulju.ulsan.kr/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do?method=selectOfrNotAncmt&methodnm=selectOfrNotAncmtRegst"
       "&not_ancmt_mgt_no=68156&homepage_pbs_yn=Y&subCheck=Y&jndinm=OfrNotAncmtEJB&context=NTIS")
r = requests.get(url, headers={**UA, "Referer": url.split("?")[0]}, timeout=40)
p("detail HTTP", r.status_code, "len", len(r.text))
html = r.text
for m in re.finditer(r"<a\b[^>]*>[^<]*(?:\.hwpx?|\.pdf|\.hwp)[^<]*</a>", html, re.I):
    p("A|", m.group(0)[:400])
for m in re.finditer(r"(?:fn_?[a-z]*[dD]own[a-zA-Z]*|download[a-zA-Z]*)\s*\(([^)]*)\)", html):
    p("JS|", m.group(0)[:200])
for m in re.finditer(r"function\s+(fn_?[a-zA-Z]*[dD]own[a-zA-Z]*)\s*\([^)]*\)\s*\{([\s\S]{0,600}?)\}", html):
    p("FN|", m.group(1), re.sub(r"\s+", " ", m.group(2))[:500])
forms = re.findall(r"<form\b[^>]*>", html, re.I)
p("forms", forms[:5])
# try direct href links
hrefs = [h for h in re.findall(r"href=[\"']([^\"']+)[\"']", html) if re.search(r"down|file", h, re.I)]
p("hrefs", hrefs[:6])
text = "\n".join(OUT)
open("/tmp/probe_out.txt", "w").write(text)
print(text)
