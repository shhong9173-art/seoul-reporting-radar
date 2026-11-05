"""probe 181: 개인정보위 '결과의 공표' 첨부 형식(파일 종류·이름·표 구조). 저장 안 함. 사람 이름은 가린다(공표 대상은 법인·기관)."""
import io, re, time
import requests

OUT = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
MASK = re.compile(r"(?<![가-힣])[가-힣]{2,3}(?=\s*(?:씨|님|대표이사|사장|회장|부회장))")


def log(*a):
    OUT.append(MASK.sub("○○", " ".join(str(x) for x in a)))


s = requests.Session()
s.headers.update(UA)
t0 = time.time()
base = "https://www.pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS258&mCode=C010040000&nttId="
for ntt in ("12608", "12454"):
    r = s.get(base + ntt, timeout=30)
    h = r.text
    i = h.find("fn_egov_downFileCnv")
    log(f"\n# nttId={ntt} {r.status_code}")
    log(" func:", re.sub(r"\s+", " ", h[i:i + 700]))
    calls = re.findall(r"fn_egov_downFile\w*\(\s*'([^']+)'\s*,\s*'([^']+)'[^)]*\)", h)
    log(" calls", calls[:6])
    names = re.findall(r"fn_egov_downFile\w*\([^)]*\)[^>]*>\s*([^<]{3,120})<", h)
    log(" names", names[:6])
    forms = re.findall(r'(/np/cmm/fms/\w+\.do)', h)
    log(" fms endpoints", sorted(set(forms)))
    for fid, sn in calls[:2]:
        for ep in ("/np/cmm/fms/FileDown.do", "/np/cmm/fms/fileDown.do"):
            u = f"https://www.pipc.go.kr{ep}?atchFileId={fid}&fileSn={sn}"
            try:
                d = s.get(u, timeout=40)
            except Exception as e:
                log("  dl fail", ep, type(e).__name__)
                continue
            cd = d.headers.get("Content-Disposition", "")
            log(f"  {ep} {d.status_code} {d.headers.get('Content-Type', '')[:40]} {len(d.content)}B cd={cd[:120]}")
            if d.status_code == 200 and d.content[:4] == b"%PDF":
                from pypdf import PdfReader
                pdf = PdfReader(io.BytesIO(d.content))
                txt = "\n".join((p.extract_text() or "") for p in pdf.pages[:3])
                log("   pdf pages", len(pdf.pages), "chars", len(txt))
                log("   head:", re.sub(r"\s+", " ", txt)[:1200])
                break
            if d.status_code == 200:
                log("   magic", d.content[:8])
                break
log(f"\n{time.time() - t0:.0f}s")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
