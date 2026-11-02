"""probe 108: 공개 꾸러미 patent-client-agents의 EUIPO 상표 검색 응답 모델 — 칸 이름만(검색 응답 구조 파악용, 호출 없음)."""
import glob, os, re, subprocess, tarfile, zipfile
out = []
d = "/tmp/pca"
os.makedirs(d, exist_ok=True)
r = subprocess.run(["python", "-m", "pip", "download", "--no-deps", "patent-client-agents", "-d", d], capture_output=True, text=True)
out.append("pip " + (r.stdout.strip().splitlines() or [""])[-1][:120] + " " + (r.stderr.strip().splitlines() or [""])[-1][:120])
for f in glob.glob(d + "/*"):
    if f.endswith(".whl"):
        zipfile.ZipFile(f).extractall(d + "/x")
    elif f.endswith(".tar.gz"):
        tarfile.open(f).extractall(d + "/x")
files = [f for f in glob.glob(d + "/x/**/*.py", recursive=True) if "euipo_trademarks" in f]
out.append("files " + ", ".join(os.path.relpath(f, d + "/x") for f in files))
for f in files:
    t = open(f, encoding="utf-8", errors="replace").read()
    fields = re.findall(r"^\s+(\w+)\s*:\s*([^=\n]+?)(?:\s*=.*)?$", t, re.M)
    classes = re.findall(r"^class\s+(\w+)", t, re.M)
    if classes:
        out.append(f"== {os.path.basename(f)} classes {classes[:30]}")
        out.append("   fields " + "; ".join(f"{a}:{b.strip()[:30]}" for a, b in fields[:90]))
    for m in re.finditer(r"alias=\"(\w+)\"", t):
        pass
    al = sorted(set(re.findall(r"alias=\"(\w+)\"", t)))
    if al:
        out.append("   aliases " + ", ".join(al[:120]))
    q = [m.group(0) for m in re.finditer(r"(?:query|params)\s*=\s*\{[^}]{0,300}\}", t)]
    if q:
        out.append("   params " + " | ".join(re.sub(r"\s+", " ", x)[:200] for x in q[:3]))
text = "\n".join(out)
open("/tmp/probe_out.txt", "w").write(text)
print(text[:800])
