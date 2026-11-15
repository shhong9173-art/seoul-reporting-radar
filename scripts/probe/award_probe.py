"""probe 246: 사전 공개본 가운데 제목에 Korea가 든 문서의 제목 칸·본문 글자 꼴. 공개 자료만, 저장 안 함."""
import json, re

import requests

OUT = []
H = {"User-Agent": "seoul-reporting-radar probe (contact: github.com/shhong9173-art/seoul-reporting-radar)", "Accept": "application/json"}
B = "https://www.federalregister.gov/api/v1/public-inspection-documents"
try:
    res = requests.get(B + "/current.json", headers=H, timeout=60).json().get("results") or []
    def ag(x):
        return [a.get("slug") or a.get("name") for a in x.get("agencies") or [] if isinstance(a, dict)]
    trade = [x for x in res if any(s in ("international-trade-administration", "international-trade-commission") for s in ag(x))]
    kor = [x for x in trade if re.search("korea", json.dumps(x), re.I)]
    OUT.append(f"ITA·ITC {len(trade)}건 · 어느 칸에든 Korea {len(kor)}건")
    for x in kor[:3]:
        OUT.append("칸: " + " | ".join(f"{k}={str(x.get(k))[:150]}" for k in ("document_number", "type", "filing_type", "filed_at", "publication_date", "title", "toc_subject", "toc_doc", "subject_1", "subject_2", "subject_3", "docket_numbers", "num_pages", "html_url", "raw_text_url", "pdf_url")))
        t = requests.get(x["raw_text_url"], headers={"User-Agent": H["User-Agent"]}, timeout=60)
        body = t.text
        OUT.append(f"raw_text HTTP {t.status_code} {len(body)}자 · content-type {t.headers.get('content-type')}")
        lines = [l.rstrip() for l in re.sub(r"<[^>]+>", "", body).split("\n")]
        keep = [l.strip() for l in lines if l.strip()]
        OUT.append("앞 줄: " + " ⏎ ".join(l[:110] for l in keep[:16]))
        idx = [i for i, l in enumerate(keep) if re.search(r"Weighted-Average|Dumping Margin|Subsidy Rate|\(percent\)|percent ad valorem", l)]
        for i in idx[:3]:
            OUT.append(f"세율 근처({i}): " + " ⏎ ".join(l[:110] for l in keep[max(0, i - 2):i + 12]))
        ap = [i for i, l in enumerate(keep) if re.match(r"(?:Appendix|List of Topics|Comment \d+)", l)]
        OUT.append(f"부록·쟁점 줄 {len(ap)}곳: " + " ⏎ ".join(keep[i][:120] for i in ap[:8]))
        OUT.append("빈 줄 비율 " + str(round(1 - len(keep) / max(1, len(lines)), 2)) + f" · 줄 수 {len(lines)}")
    # 한 문서 주소(json)로도 열리는지
    if kor:
        j = requests.get(f"{B}/{kor[0]['document_number']}.json", headers=H, timeout=60)
        OUT.append(f"문서 한 건 주소 HTTP {j.status_code} · 키 {sorted(j.json().keys())[:40] if j.status_code == 200 else j.text[:80]}")
except Exception as e:
    OUT.append(f"실패 {type(e).__name__}: {str(e)[:200]}")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
