"""probe 182: 개인정보위 결과의 공표 — 운영과 같은 pypdf<6로 읽은 글자(앞 600자, 특수문자 코드), 첨부 형식(magic)별 수. 저장 안 함.
공표 대상은 법인·기관(공개 공표). 사람 이름처럼 보이는 것은 가린다."""
import io, re, sys, time
import requests

sys.path.insert(0, "scripts")
import official_sanctions as osn  # noqa: E402

OUT = []
MASK = re.compile(r"(?<![가-힣])[가-힣]{2,3}(?=\s*(?:씨|님))")


def log(*a):
    OUT.append(MASK.sub("○○", " ".join(str(x) for x in a)))


import pypdf
log("pypdf", pypdf.__version__)
s = requests.Session()
s.headers.update(osn.UA)
t0 = time.time()
ids = []
for n in range(1, 5):
    r = s.get(f"{osn.PIPC_LIST}&pageIndex={n}", timeout=30)
    got = [x for x in dict.fromkeys(re.findall(r"selectBoardArticle\.do[^\"']*?nttId=(\d+)", r.text)) if x not in ids]
    if not got:
        break
    ids += got
log("posts", len(ids))
magic, shown = {}, 0
for ntt in ids:
    v = s.get(osn.PIPC_VIEW + ntt, timeout=30)
    files = re.findall(r"fn_egov_downFile\w*\(\s*'([^']+)'\s*,\s*'([^']+)'(?:\s*,\s*'([^']*)')?", v.text)
    for fid, sn, ext in files[:3]:
        f = s.get(osn.PIPC_FILE.format(fid, sn), headers={"Referer": osn.PIPC_VIEW + ntt}, timeout=40)
        m = f.content[:4]
        key = f"{m!r}:{ext}"
        magic[key] = magic.get(key, 0) + 1
        if m == b"%PDF" and shown < 3:
            shown += 1
            txt = osn.pdf_text(f.content, 6)
            flat = re.sub(r"\s+", " ", txt)
            log(f"\n# {ntt} chars={len(txt)}")
            log(" head:", flat[:700])
            i = flat.find("보호법")
            log(" around 보호법:", [hex(ord(c)) for c in flat[max(0, i - 4):i + 3]] if i >= 0 else None)
            log(" rows parsed:", len(osn.pipc_rows(txt)))
            log(" raw lines:", txt.splitlines()[:25])
log("\nmagic", magic)
log(f"{time.time() - t0:.0f}s")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
