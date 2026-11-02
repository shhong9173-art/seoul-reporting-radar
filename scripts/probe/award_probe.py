"""probe 104: 새올 공고 상세의 첨부 파일 내려받기 경로(울주 68156 고려아연 #2ASU) — 링크 모양, hwpx 본문 글자, pdf 글자 수."""
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
for m in re.finditer(r"FileDown\.jsp", html):
    p("CTX|", re.sub(r"\s+", " ", html[max(0, m.start() - 300): m.start() + 300]))
from urllib.parse import quote, urlencode
links = re.findall(r"goDownLoad\('([^']*)','([^']*)','([^']*)'\)", html)
base = "http://eminwon.ulju.ulsan.kr/emwp/jsp/ofr/FileDown.jsp"
for user, sysn, path in links:
    if not (user.endswith("공사].hwpx") or user.endswith(".pdf")):
        continue
    for enc in ("utf-8", "euc-kr"):
        try:
            q = urlencode({"user_file_nm": user, "sys_file_nm": sysn, "file_path": path}, encoding=enc)
            d = requests.get(base + "?" + q, headers={**UA, "Referer": url}, timeout=60)
            p("DL", enc, user[-30:], "HTTP", d.status_code, "type", d.headers.get("content-type"), "bytes", len(d.content), "head", d.content[:4])
            if d.status_code == 200 and d.content[:2] == b"PK":
                z = zipfile.ZipFile(io.BytesIO(d.content))
                names = z.namelist()
                p("  zip", [n for n in names if "section" in n.lower() or "Preview" in n][:6])
                sec = [n for n in names if re.search(r"Contents/section\d+\.xml", n)]
                txt = " ".join(re.sub(r"<[^>]+>", " ", z.read(n).decode("utf-8", "ignore")) for n in sec)
                txt = re.sub(r"\s+", " ", txt)
                p("  text chars", len(txt))
                p("  TEXT|", txt[:1500])
                break
            if d.status_code == 200 and d.content[:4] == b"%PDF":
                from pypdf import PdfReader
                rd = PdfReader(io.BytesIO(d.content))
                t = " ".join((pg.extract_text() or "") for pg in rd.pages)
                p("  pdf pages", len(rd.pages), "chars", len(t), "TEXT|", re.sub(r"\s+", " ", t)[:600])
                break
        except Exception as e:
            p("DL ERR", enc, type(e).__name__, str(e)[:100])
text = "\n".join(OUT)
open("/tmp/probe_out.txt", "w").write(text)
print(text)
