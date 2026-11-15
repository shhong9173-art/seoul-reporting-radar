"""probe 248: 단독 원천 후보가 열리는지(상태·제목·관련 줄 몇 개만). 공개 페이지만, 저장 안 함."""
import re

import requests

OUT = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36", "Accept-Language": "en,ko;q=0.8"}


def look(name, url, pats, **kw):
    try:
        r = requests.get(url, headers=UA, timeout=40, **kw)
        body = r.text
        title = re.sub(r"\s+", " ", (re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I) or [None, ""])[1])[:80]
        text = re.sub(r"\s+", " ", re.sub(r"<(script|style)\b.*?</\1>", " ", body, flags=re.S | re.I))
        plain = re.sub(r"<[^>]+>", " ", text)
        hits = []
        for p in pats:
            for m in list(re.finditer(p, plain, re.I))[:3]:
                hits.append(re.sub(r"\s+", " ", plain[max(0, m.start() - 90):m.end() + 130]).strip())
        links = [h for h in re.findall(r'href="([^"]+)"', body) if re.search(r"combin|merger|notif|frnotice|ajgs|jyzjz|처분|disposal|xls|json|api", h, re.I)][:8]
        OUT.append(f"[{name}] HTTP {r.status_code} · {len(body)}자 · 제목 {title!r} · 최종 주소 {r.url[:90]}")
        for h in hits[:5]:
            OUT.append("   · " + h[:300])
        if links:
            OUT.append("   링크: " + " | ".join(l[:90] for l in links))
    except Exception as e:  # noqa: BLE001
        OUT.append(f"[{name}] 실패 {type(e).__name__}: {str(e)[:120]}")


look("미 상무부 ACCESS 관보 고시 목록", "https://access.trade.gov/public/FRNoticesListLayout.aspx", [r"Oil Country[^|]{0,80}Korea", r"Korea[^|]{0,60}(?:Final|Preliminary) (?:Results|Determination)", r"\d{1,2}/\d{1,2}/2026"])
look("미 상무부 ACCESS frnotices", "https://access.trade.gov/frnotices", [r"Korea", r"Signed|Signature|Date"])
look("EU 기업결합 사건 검색", "https://competition-cases.ec.europa.eu/search?caseInstrument=M&sortField=caseLastDecisionDate&sortOrder=DESC", [r"POSCO|Hyundai|Hanwha|LG Chem"])
look("EU 기업결합 최근 신고(옛 목록)", "https://ec.europa.eu/competition/mergers/cases/index/by_notif_date.html", [r"POSCO|HYUNDAI|HANWHA|LG CHEM|SK ", r"20\d\d"])
look("EU 사건 API 추정", "https://competition-cases.ec.europa.eu/api/v1/cases?caseInstrument=M&pageSize=5", [r"caseNumber|caseTitle"])
look("인도 CCI 기업결합", "https://www.cci.gov.in/combination/summary-of-combinations-under-review", [r"POSCO|Hyundai|Kia|LG|Hanwha|JSW", r"C-20\d\d/\d\d/\d+"])
look("인도 CCI 첫 화면", "https://www.cci.gov.in/", [r"combination"])
look("중국 SAMR 간이사건 공시", "https://www.samr.gov.cn/fldes/ajgs/jyaj/", [r"现代|起亚|浦项|韩华|LG|SK", r"经营者集中"])
look("중국 SAMR 반독점국", "https://www.samr.gov.cn/fldes/", [r"简易案件|公示"])
look("통합환경허가시스템", "https://ieps.nier.go.kr/", [r"행정처분|처분\s*현황|정보공개"])
look("환경부 통합허가 행정처분 공개", "https://ieps.nier.go.kr/web/board/5/?menu=41", [r"행정처분|조업정지|과징금|포스코|현대제철"])
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
