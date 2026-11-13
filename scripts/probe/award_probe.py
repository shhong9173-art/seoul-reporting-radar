"""probe 223: 새 원천 후보가 GitHub에서 열리는지·어떤 꼴인지 본다(공개 페이지만, 저장 안 함, 원천마다 1~3번 요청)."""
import re

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
OUT = []
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "ko,en;q=0.8"})


def text_of(html):
    t = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", html or "", flags=re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t)).strip()


def look(label, url, href=None, words=(), show=220, method="GET", data=None, n_href=12):
    try:
        r = S.request(method, url, data=data, timeout=30, allow_redirects=True)
    except Exception as e:  # noqa: BLE001
        OUT.append(f"## {label}: 실패 {type(e).__name__} {str(e)[:90]}")
        return ""
    html = r.text or ""
    title = (re.search(r"<title[^>]*>([\s\S]*?)</title>", html, re.I) or [None, ""])[1].strip()[:80]
    t = text_of(html)
    OUT.append(f"## {label}: {r.status_code} {len(html)}자 ct={r.headers.get('content-type', '')[:30]} 끝주소={r.url[:110]} 제목「{title}」")
    if words:
        OUT.append("   낱말: " + " ".join(f"{w}={len(re.findall(w, html, re.I))}" for w in words))
    if href:
        links = list(dict.fromkeys(m for m in re.findall(r'href="([^"]+)"', html) if re.search(href, m, re.I)))
        OUT.append(f"   링크({len(links)}): " + " | ".join(x[:95] for x in links[:n_href]))
    if show:
        OUT.append("   글: " + t[:show])
    return html


# 1. 영국 TRA 공개기록
h = look("TRA 목록", "https://public-file.trade-remedies.service.gov.uk/", href=r"/case/[a-z]{2}\d{4}$", words=("Korea",), show=0, n_href=6)
h = look("TRA ad0092", "https://public-file.trade-remedies.service.gov.uk/case/ad0092", href=r"/submission/", words=("LG Chem", "Hanwha", "Government of Korea", "<tr"), show=0, n_href=4)
rows = re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", h)
for row in rows[1:4]:
    OUT.append("   행: " + " ¦ ".join(text_of(c)[:60] for c in re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", row)))
h = look("TRA 제출 1239", "https://public-file.trade-remedies.service.gov.uk/case/ad0092/submission/1239", href=r"\.pdf|/download|/file|document", show=300)
h = look("TRA 제출 LG", "https://public-file.trade-remedies.service.gov.uk/case/ad0092/submission/s-0000012417-j7d0", href=r"\.pdf|/download|/file|document", show=300)
# 2. 호주 ADC · EU TRON · 캐나다
look("호주 ADC 현재 사건", "https://www.industry.gov.au/anti-dumping-commission/current-cases-and-electronic-public-record-epr", href=r"epr|case", words=("Korea",), show=200)
look("EU TRON 진행", "https://tron.trade.ec.europa.eu/investigations/ongoing", href=r"case", words=("Korea",), show=200)
# 3. 국내 자동차
look("ev.or.kr 지급대상 차종", "https://ev.or.kr/nportal/buySupprt/initSubsidyTargetVehicleAction.do", href=r"Subsidy|Vehicle|buySupprt", words=("아이오닉", "기아", "BMW", "<tr"), show=200)
look("car.go.kr 첫 화면", "https://www.car.go.kr/", href=r"recall|grts|free|stat|ri/|rs/", show=120, n_href=20)
look("car.go.kr 리콜현황", "https://www.car.go.kr/ri/stat/list.do", href=r"view|detail", words=("리콜", "무상", "<tr"), show=200)
look("car.go.kr 무상점검", "https://www.car.go.kr/ri/grts/list.do", href=r"view|detail", words=("무상", "<tr"), show=200)
look("KENCIS", "https://www.kencis.or.kr/", href=r"cert|list|open", show=150)
look("전파연구원 적합성평가 검색", "https://www.rra.go.kr/ko/license/A_c_search.do", href=r"license", words=("현대", "<tr"), show=150)
look("통합환경허가", "https://ieps.nier.go.kr/", href=r"open|pblc|public|info|list", show=150, n_href=15)
# 4. 미국 주 정부·연방
look("테네시 FastTrack", "https://www.tn.gov/transparenttn/state-financial-overview/open-ecd/openecd/fasttrack-project-database.html", href=r"csv|xlsx|json|data", words=("Hankook", "LG Chem", "Hyundai", "<tr"), show=150)
look("TVA 이사회", "https://www.tva.com/about-tva/our-leadership/board-of-directors/board-meetings", href=r"board|agenda|\.pdf", words=("Korea Zinc", "agenda"), show=150)
look("조지아 항만청", "https://gaports.com/", href=r"board|press|news", show=100)
look("NHTSA vPIC MID", "https://vpic.nhtsa.dot.gov/mid/", href=r"mid/", show=150)
look("CARB EO", "https://ww2.arb.ca.gov/new-vehicle-and-engine-certification-executive-orders", href=r"executive|eo|cert", show=150)
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
