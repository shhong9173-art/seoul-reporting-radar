"""probe 186: 개인정보위 결과의 공표 그림(PNG) 첨부 2건 — tesseract(kor) 글자와 pipc_rows 결과. 저장 안 함. 공표 대상은 법인·기관."""
import re, subprocess, sys, tempfile, time
import requests

sys.path.insert(0, "scripts")
import official_sanctions as osn  # noqa: E402

OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


s = requests.Session()
s.headers.update(osn.UA)
t0 = time.time()
log("tesseract", subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True).stdout.replace("\n", " ")[:200])
for ntt in ("12388", "12358"):
    v = s.get(osn.PIPC_VIEW + ntt, timeout=30)
    for fid, sn in re.findall(r"fn_egov_downFile\w*\(\s*'([^']+)'\s*,\s*'([^']+)'", v.text)[:3]:
        f = s.get(osn.PIPC_FILE.format(fid, sn), headers={"Referer": osn.PIPC_VIEW + ntt}, timeout=40)
        if f.content[:4] != b"\x89PNG":
            continue
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fp:
            fp.write(f.content)
        for psm in ("6", "4"):
            r = subprocess.run(["tesseract", fp.name, "stdout", "-l", "kor", "--psm", psm], capture_output=True, text=True, timeout=120)
            txt = r.stdout
            rows = osn.pipc_rows(txt)
            log(f"\n# {ntt} psm {psm} chars {len(txt)} rows {len(rows)} {[(x['org'], x['date'], x['inst'][:30]) for x in rows][:6]}")
            log("  head:", re.sub(r"\s+", " ", txt)[:700])
log(f"\n{time.time() - t0:.0f}s")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
