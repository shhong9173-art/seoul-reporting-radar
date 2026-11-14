"""probe 233: DGTR 이해관계자 명단 PDF — 번호 줄이 이어지는지, 한 곳이 몇 줄인지, 번호가 건너뛰는 자리의 줄 꼴. 공개 PDF만, 저장 안 함. 이메일은 가린다."""
import io
import re
import time

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
OUT = []
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "en,ko;q=0.8"})
B = "https://www.dgtr.gov.in/en/anti-dumping-cases/"
CASES = [("phenol", B + "anti-dumping-investigation-concerning-imports-phenol-saudi-arabia-singapore"),
         ("acetone", B + "anti-dumping-investigation-concerning-imports-acetone-republic-singapore"),
         ("chisel", B + "anti-dumping-investigation-concerning-imports-alloy-steel-chisel-tool-and")]
ENTRY = re.compile(r"^(\d{1,3})[.)](?:\s|$)")
HEAD = re.compile(r"^(?:S\.?\s*N(?:o|\.)|Sl\.?\s*No|Sr\.?\s*No|Name of (?:the )?(?:Interested|Part|Compan|Entit))", re.I)


def txt(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h or "")).strip()


def mask(x):
    return re.sub(r"[\w.+-]+@[\w.-]+", "<mail>", x)


for name, url in CASES:
    time.sleep(2)
    try:
        h = S.get(url, timeout=60).text or ""
        rows = []
        for x in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", h, re.I):
            cells = [txt(c) for c in re.findall(r"<td[^>]*>([\s\S]*?)</td>", x, re.I)]
            href = re.findall(r'href="([^"]+)"', x)
            if len(cells) >= 3 and re.search(r"\d{2}/\d{2}/\d{4}", cells[-1]) and re.search(r"interested\s+part", cells[1], re.I) and href:
                rows.append((cells[-1][-10:], href[0]))
        d, link = max(rows, key=lambda x: x[0][6:] + x[0][3:5] + x[0][:2])
        time.sleep(2)
        import pypdf
        doc = pypdf.PdfReader(io.BytesIO(S.get(link, timeout=90).content))
        lines = [re.sub(r"\s+", " ", x).strip() for x in "\n".join((pg.extract_text() or "") for pg in doc.pages[:12]).splitlines()]
        lines = [x for x in lines if x]
        head = next((i for i, x in enumerate(lines) if HEAD.match(x)), None)
        OUT.append(f"## {name} [{d}] 줄 {len(lines)} · 표 머리 줄 {head} 「{mask(lines[head])[:40] if head is not None else ''}」 · 머리 뒤 8줄: " + " ⏎ ".join(mask(x)[:40] for x in lines[(head or 0) + 1:(head or 0) + 9]))
        nums = [(i, int(ENTRY.match(x).group(1))) for i, x in enumerate(lines) if i > (head or 0) and ENTRY.match(x)]
        OUT.append("   번호 줄(줄번호:번호): " + " ".join(f"{i}:{n}" for i, n in nums)[:900])
        seq = [n for _, n in nums]
        gaps = [(nums[k][0], nums[k][1], nums[k + 1][0], nums[k + 1][1]) for k in range(len(nums) - 1) if nums[k + 1][1] != nums[k][1] + 1]
        spans = [nums[k + 1][0] - nums[k][0] for k in range(len(nums) - 1)]
        OUT.append(f"   번호 {len(seq)}개 · 처음 {seq[:3]} · 끝 {seq[-3:]} · 한 곳 줄 수 최대 {max(spans) if spans else 0}·중간 {sorted(spans)[len(spans) // 2] if spans else 0} · 12줄 넘는 곳 {sum(1 for s in spans if s > 12)} · 건너뛴 자리 {len(gaps)}")
        for a, an, b, bn in gaps[:4]:
            OUT.append(f"     건너뜀 {an}→{bn} (줄 {a}~{b}): " + " ⏎ ".join(mask(x)[:60] for x in lines[a:min(b + 2, a + 30)]))
        digits = [(i, x) for i, x in enumerate(lines) if i > (head or 0) and re.match(r"^\d{1,3}\s*[.)]?$", x) and not ENTRY.match(x)]
        OUT.append(f"   점 없는 숫자만 있는 줄 {len(digits)}개: " + " ".join(f"{i}:{x}" for i, x in digits[:20]))
        tail = nums[-1][0] if nums else 0
        OUT.append(f"   마지막 번호 뒤 줄({len(lines) - tail}줄): " + " ⏎ ".join(mask(x)[:70] for x in lines[tail:tail + 16]))
        if name == "phenol":
            OUT.append("   줄 222~236: " + " ⏎ ".join(f"[{i}] {mask(lines[i])[:60]}" for i in range(222, min(237, len(lines)))))
    except Exception as e:  # noqa: BLE001
        OUT.append(f"## {name}: 실패 {type(e).__name__} {str(e)[:80]}")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
