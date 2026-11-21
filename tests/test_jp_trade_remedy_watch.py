"""일본 무역구제 공고 감시 — 탐침(11-21)의 실제 재무성 목록·상세 쪽 글(일본어) 모양으로."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import jp_trade_remedy_watch as w  # noqa: E402

KST = w.KST
NOW = dt.datetime(2026, 11, 21, 11, 40, tzinfo=KST)
F = "https://www.mof.go.jp/policy/customs_tariff/trade/plan/futou/"
GALV = "大韓民国産及び中華人民共和国産溶融亜鉛めっき鋼帯及び鋼板"


def li(slug, title, date):
    return f'<li><a href="{F}{slug}.html">{title}</a>（{date}）</li>'


def page(*items):
    return ('<html><body><nav><ul><li><a href="/policy/index.html">財務省の政策</a></li></ul></nav><main><h1>不当廉売関税</h1>'
            '<h2>不当廉売関税に関する決定等</h2><ul>' + "".join(items) +
            '<li><a href="https://warp.ndl.go.jp/">過去の掲載資料（国立国会図書館）</a></li></ul></main></body></html>')


L_SUS = li("ka20261027", "中華人民共和国産若しくは台湾、澎湖諸島、金門及び馬祖から成る独立の関税地域産ニッケル系ステンレス冷延鋼帯及び冷延鋼板に対する不当廉売関税の課税を決定しました",
           "令和8年10月27日")
L_PROV = li("ka20260804", GALV + "に対する暫定的な不当廉売関税の課税を決定しました", "令和8年8月4日")
L_EXT = li("ka20260724-2", GALV + "に対する不当廉売関税の課税に関する調査の期間を延長します", "令和8年7月24日")
L_PRE = li("ka20260724-1", " " + GALV + "に対する不当廉売関税の課税に関する調査において、不当廉売がされた貨物の輸入の事実及び当該輸入の本邦の産業に与える"
           "実質的な損害等の事実を推定することについての決定（仮の決定）をしました", "令和8年7月24日")
L_BPA = li("ka20260724-3", "大韓民国産並びに台湾、澎湖諸島、金門及び馬祖から成る独立の関税地域産ビスフェノールＡに対する不当廉売関税の課税に関する調査の期間を延長します",
           "令和8年7月24日")
L_KOH = li("ka20251225", "大韓民国産及び中華人民共和国産水酸化カリウムに対する不当廉売関税の課税期間の延長に関する調査を開始します", "令和7年12月25日")
L_HR = li("ka20260601-1", "大韓民国産、中華人民共和国産並びに台湾、澎湖諸島、金門及び馬祖から成る独立の関税地域産熱延鋼帯及び鋼板に対する不当廉売関税の課税に関する調査を開始します",
          "令和8年6月1日")
L_FINAL = li("ka20261204", GALV + "に対する不当廉売関税の課税を決定しました", "令和8年12月4日")

D_PRE = ('<html><body><main><h1>' + GALV + 'に対する…（仮の決定）をしました</h1>'
         '<p>財務省及び経済産業省は、令和７年４月２８日に日本製鉄株式会社、日鉄鋼板株式会社、株式会社神戸製鋼所及び株式会社ヨドコウ（申請書掲載順）から'
         '「大韓民国産及び中華人民共和国（注１）産溶融亜鉛めっき鋼帯及び鋼板（注２）に対する不当廉売関税を課することを求める書面」が提出されたことを受け、'
         '同年８月１３日から、当該不当廉売関税の課税の要否に関する両省合同の調査を実施してまいりました。</p>'
         '<p>調査において、…事実を推定するに至ったことから、本日付けで仮の決定をいたしました。（本日付け告示）</p>'
         '<p><a href="/policy/customs_tariff/trade/plan/futou/ka20260724-1a.pdf">財務省告示第２１０号</a></p></main></body></html>')
D_PROV = ('<html><body><main><p>本日、大韓民国及び中華人民共和国（注1）（以下「中国」という。）を原産地とする溶融亜鉛めっき鋼帯及び鋼板（注2）に対して暫定的な不当廉売関税を課する政令が閣議決定されました。</p>'
          '<p>今後、本年８月７日に政令が公布され、同月８日から同年12月７日までの間、大韓民国及び中国を原産地とする溶融亜鉛めっき鋼帯及び鋼板に対して、暫定的な不当廉売関税が課されることとなります。</p>'
          '<p>・ 本年７月30日、関税・外国為替等審議会（関税分科会特殊関税部会）から、…暫定的に課することが適当である旨の答申が提出されました（暫定的な不当廉売関税率は29.2～55.3％）。</p>'
          '</main></body></html>')
D_EXT = ('<html><body><main><p>財務省及び経済産業省は、…調査の期間を４か月延長して令和８年１２月１２日までとすることとしました。</p>'
         '<p>関税定率法上、調査は原則として１年以内に終了するものとされていますが、必要がある場合には６か月以内に限り延長することができます。</p></main></body></html>')


C = "https://www.mof.go.jp/about_mof/councils/customs_foreign_exchange/sub-of_customs/proceedings_tokusyu/material/"


def council_index(*dates):
    rows = "".join(f'<p><a href="./kanb{d.replace("-", "")}.html">令和{int(d[:4]) - 2018}年{int(d[5:7])}月{int(d[8:])}日開催</a></p>' for d in dates)
    return f'<html><body><main><h2>配付資料等</h2><ul><li>{rows}</li></ul></main></body></html>'


MEETING = ('<html><body><main><h1>関税・外国為替等審議会 関税分科会 特殊関税部会 （令和８年11月20日開催）配付資料</h1><ul>'
           '<li><a href="./20261120/kanb20261120nittei.pdf">議事日程(PDF:90KB)</a></li>'
           '<li><a href="./20261120/kanb20261120siryo1-1.pdf">（資料１－１）諮問書(PDF:184KB)</a></li>'
           '<li><a href="./20261120/kanb20261120siryo2-1.pdf">（資料２－１）溶融亜鉛めっき鋼帯及び鋼板産業の現状(PDF:290KB)</a></li>'
           '<li><a href="./20261120/kanb20261120siryo2-2.pdf">（資料２－２）大韓民国産及び中華人民共和国産溶融亜鉛めっき鋼帯及び鋼板に対する不当廉売関税の課税(PDF:729KB)</a></li>'
           '<li><a href="./20261120/kanb20261120siryo2-3.pdf">（資料２－３）調査結果報告書(PDF:3886KB)</a></li>'
           '<li><a href="./20261120/kanb20261120siryo3-2.pdf">（資料３－２）大韓民国産及び台湾産ビスフェノールAに対する不当廉売関税の課税(PDF:725KB)</a></li>'
           '<li><a href="./20261120/kanb20261120siryo4-2.pdf">（資料４－２）大韓民国産及び中華人民共和国産水酸化カリウムに対する不当廉売関税の課税期間の延長(PDF:714KB)</a></li>'
           '</ul></main></body></html>')
PDF_GALV = "表3 不当廉売関税率 大韓民国 POSCO 29.2% KG Dongbu サンプリング調査非対象者 30.6% … 不当廉売関税を課することが適当 … 課税期間は5年間とする"
PDF_BPA = "不当廉売関税(韓国供給者LG Chem, Ltd.を除く)を課することが適当 KUMHO P&B CHEMICALS, INC. 7.0% … ５年間"
PDF_KOH = "課税期間を延長することが適当 … 5年間"


class Resp:
    def __init__(self, text, code=200):
        self.text, self.status_code, self.encoding = text, code, None
        self.content = text.encode() if isinstance(text, str) else text


def fake(pages, fail=()):
    calls = []

    def get(url, headers=None, timeout=None):
        calls.append(url)
        if url in fail:
            raise ConnectionError("x")
        if url in pages:
            return Resp(pages[url])
        if url == w.COUNCIL_INDEX:
            return Resp(council_index("2026-07-30"))   # 기본: 오래된 회의 하나(기준선)
        if url.endswith("index.html"):
            return Resp(page())   # 상계관세·세이프가드 목록: 날짜 줄 없음
        return Resp("", 404)
    get.calls = calls
    return get


def run(listing, details=None, prev=None, now=NOW, fail=(), extra=None):
    pages = {w.INDEXES[0][2]: listing, **{F + k + ".html": v for k, v in (details or {}).items()}, **(extra or {})}
    get = fake(pages, fail)
    return w.run(now, prev, get=get, sleep=lambda s: None), get


class Parse(unittest.TestCase):
    def test_index_dated_rows_only(self):
        rows = w.parse_index(page(L_SUS, L_PROV, L_PRE), "AD", w.INDEXES[0][2])
        self.assertEqual([r["date"] for r in rows], ["2026-10-27", "2026-08-04", "2026-07-24"])
        self.assertTrue(rows[2]["title"].startswith("大韓民国産"))   # 앞 공백 제거
        self.assertEqual(rows[1]["url"], F + "ka20260804.html")

    def test_wanted_korea_or_beat_safeguard(self):
        rows = w.parse_index(page(L_SUS, L_PROV, L_KOH), "AD", w.INDEXES[0][2])
        self.assertEqual([w.wanted(r) for r in rows], [False, True, True])
        sg = {"title": "鉄鋼製品に対する緊急関税の課税に関する調査を開始します", "index": "SG"}
        self.assertTrue(w.wanted(sg))
        self.assertFalse(w.wanted({**sg, "title": "ねぎに対する緊急関税の調査を開始します"}))

    def test_kinds_order(self):
        k = lambda li_html: w.kind_of(w.parse_index(page(li_html), "AD", "")[0]["title"])  # noqa: E731
        self.assertEqual(k(L_PRE), "예비 판정(가결정)")
        self.assertEqual(k(L_PROV), "잠정 관세 결정")
        self.assertEqual(k(L_EXT), "조사 기간 연장")
        self.assertEqual(k(L_KOH), "일몰 재심(과세 기간 연장 조사) 개시")
        self.assertEqual(k(L_HR), "조사 개시")
        self.assertEqual(k(L_FINAL), "확정 관세 결정")
        self.assertEqual(w.kind_of("大韓民国産炭酸二カリウムに対する不当廉売関税の課税期間の延長を決定しました"), "과세 기간 연장 결정(일몰 재심 결과)")

    def test_products_and_tiers(self):
        self.assertEqual(w.product_ko(GALV)[0], "용융아연도금강판")
        self.assertEqual(w.product_ko("大韓民国産…ビスフェノールＡ")[0], "비스페놀A")
        self.assertFalse(w.product_ko("水酸化カリウム")[2])
        self.assertEqual(w.tier_of("잠정 관세 결정", True), "A")
        self.assertEqual(w.tier_of("조사 기간 연장", True), "B")
        self.assertEqual(w.tier_of("일몰 재심(과세 기간 연장 조사) 개시", False), "B")
        self.assertEqual(w.tier_of("조사 기간 연장", False), "C")
        self.assertEqual(w.case_key(GALV + "に対する暫定的な…"), GALV)

    def test_detail_facts(self):
        d = w.parse_detail(D_PRE, "2026-07-24")
        self.assertIn("日本製鉄株式会社", d["applicants"])
        self.assertNotIn("申請書掲載順", d["applicants"])
        self.assertEqual(d["pdfs"][0]["url"], F + "ka20260724-1a.pdf")
        self.assertTrue(any("仮の決定" in f for f in d["facts"]))
        p = w.parse_detail(D_PROV, "2026-08-04")
        self.assertEqual(p["rates"], "29.2~55.3%")
        self.assertEqual(p["dutyTo"], "2026-12-07")
        e = w.parse_detail(D_EXT, "2026-07-24")
        self.assertEqual(e["until"], "2026-12-12")
        self.assertEqual(e["dutyTo"], "")

    def test_company_names_in_body(self):
        d = w.parse_detail("<main><p>輸出者ＰＯＳＣＯ及びポスコ、現代製鉄株式会社の個別税率は次のとおり。</p></main>", "2026-12-04")
        self.assertIn("포스코", d["companies"])
        self.assertIn("현대제철", d["companies"])


class Run(unittest.TestCase):
    def test_first_run_is_baseline_and_reads_details(self):
        doc, get = run(page(L_SUS, L_PROV, L_EXT, L_PRE), {"ka20260804": D_PROV, "ka20260724-2": D_EXT, "ka20260724-1": D_PRE})
        self.assertEqual(doc["status"], "ok")
        self.assertEqual(doc["events"], [])
        self.assertEqual(len(doc["entries"]), 3)    # 중국·대만만인 스테인리스는 뺀다
        ext = next(e for e in doc["entries"] if e["url"].endswith("ka20260724-2.html"))
        self.assertEqual(ext["detail"]["until"], "2026-12-12")
        self.assertEqual(doc["checks"][0]["korea"], 3)
        self.assertEqual(doc["detailPending"], 0)

    def test_new_entry_becomes_event_with_detail(self):
        doc, _ = run(page(L_PROV, L_EXT), {"ka20260804": D_PROV, "ka20260724-2": D_EXT})
        D_FINAL = D_PROV.replace("暫定的な不当廉売関税率", "不当廉売関税率").replace("同月８日から同年12月７日までの間", "同月８日から令和13年12月7日までの間")
        doc2, _ = run(page(L_FINAL, L_PROV, L_EXT), {"ka20261204": D_FINAL}, prev=doc, now=NOW + dt.timedelta(days=13))
        self.assertEqual(doc2["fresh"], 1)
        ev = doc2["events"][0]
        self.assertEqual(ev["id"], "jptr:ka20261204")
        self.assertEqual(ev["tier"], "A")
        self.assertEqual(ev["product"], "용융아연도금강판")
        self.assertIn("확정 관세 결정", ev["text"])
        self.assertIn("세율 29.2~55.3%", ev["text"])
        self.assertIn("관세 부과 2031-12-07까지", ev["text"])

    def test_detail_failure_then_fill_later(self):
        doc, _ = run(page(L_PROV), {"ka20260804": D_PROV})
        doc2, _ = run(page(L_HR, L_PROV), {}, prev=doc, fail=(F + "ka20260601-1.html",))
        self.assertEqual(doc2["fresh"], 1)
        self.assertIn("상세 쪽 못 읽음", doc2["events"][0]["text"])
        self.assertEqual(doc2["status"], "partial")
        detail = '<main><p>本日、…調査を開始しました。調査は原則として１年以内に終了します。</p></main>'
        doc3, _ = run(page(L_HR, L_PROV), {"ka20260601-1": detail}, prev=doc2)
        self.assertEqual(doc3["fresh"], 0)
        self.assertEqual(len(doc3["events"]), 1)
        self.assertNotIn("상세 쪽 못 읽음", doc3["events"][0]["text"])
        self.assertIn("updatedAt", doc3["events"][0])

    def test_list_failure_keeps_previous(self):
        doc, _ = run(page(L_PROV), {"ka20260804": D_PROV})
        doc2, _ = run(page(L_PROV), prev=doc, fail=tuple(u for _, _, u in w.INDEXES))
        self.assertEqual(doc2["status"], "failed")
        self.assertEqual(len(doc2["entries"]), 1)
        self.assertTrue(doc2["stale"])

    def test_empty_ad_list_is_failure_not_zero(self):
        doc, _ = run(page())
        self.assertEqual(doc["checks"][0]["status"], "failed")
        self.assertIn("형식", doc["checks"][0]["error"])

    def test_detail_budget(self):
        items = [li(f"ka202606{i:02d}", f"大韓民国産鋼製品{i}に対する不当廉売関税の課税に関する調査を開始します", f"令和8年6月{i}日") for i in range(1, 8)]
        doc, get = run(page(*items), {f"ka202606{i:02d}": "<main><p>本日、調査を開始しました。</p></main>" for i in range(1, 8)})
        detail_calls = [u for u in get.calls if not u.endswith("index.html")]
        self.assertEqual(len(detail_calls), w.DETAIL_BUDGET)
        self.assertEqual(doc["detailPending"], 7 - w.DETAIL_BUDGET)


class Council(unittest.TestCase):
    def setUp(self):
        self._pdf = w.pdf_text
        w.pdf_text = lambda content: w.norm(content.decode())

    def tearDown(self):
        w.pdf_text = self._pdf

    def test_index_and_meeting_parse(self):
        rows = w.parse_council_index(council_index("2026-11-20", "2026-10-19"))
        self.assertEqual(rows, [{"url": C + "kanb20261120.html", "date": "2026-11-20"}, {"url": C + "kanb20261019.html", "date": "2026-10-19"}])
        mats = w.parse_meeting(MEETING, C + "kanb20261120.html")
        self.assertEqual(len(mats), 7)
        self.assertEqual(mats[3]["url"], C + "20261120/kanb20261120siryo2-2.pdf")
        self.assertFalse(mats[3]["title"].endswith("KB)"))
        items = w.council_items(mats)
        self.assertEqual([(i["productKo"], i["kind"], i["beat"]) for i in items],
                         [("용융아연도금강판", "관세 부과(확정)", True), ("비스페놀A", "관세 부과(확정)", True), ("수산화칼륨", "과세 기간 연장(일몰)", False)])

    def test_facts_from_pdf_text(self):
        g = w.council_facts(w.norm(PDF_GALV))
        self.assertEqual((g["recommends"], g["years"]), (True, 5))
        self.assertIn("포스코", g["companies"])
        self.assertIn("KG스틸", g["companies"])
        b = w.council_facts(w.norm(PDF_BPA))
        self.assertEqual(b["excluded"], ["LG화학"])
        self.assertIn("LG Chem", b["excludedRaw"][0])
        self.assertEqual(b["years"], 5)
        self.assertNotIn("금호석유화학", b["companies"])   # Kumho P&B는 계열사 — 출입처 아님

    def test_recent_meeting_is_event_even_on_first_run(self):
        extra = {w.COUNCIL_INDEX: council_index("2026-11-20", "2026-07-30"), C + "kanb20261120.html": MEETING,
                 C + "20261120/kanb20261120siryo2-2.pdf": PDF_GALV, C + "20261120/kanb20261120siryo3-2.pdf": PDF_BPA,
                 C + "20261120/kanb20261120siryo4-2.pdf": PDF_KOH}
        doc, get = run(page(L_PROV), {"ka20260804": D_PROV}, extra=extra)
        self.assertNotIn(C + "kanb20260730.html", get.calls)      # 오래된 회의는 기준선 — 열지 않는다
        ev = [e for e in doc["events"] if e["id"].startswith("jpcouncil:")]
        self.assertEqual(len(ev), 1)
        self.assertEqual((ev[0]["id"], ev[0]["tier"], ev[0]["product"]), ("jpcouncil:20261120", "A", "용융아연도금강판"))
        self.assertIn("① 용융아연도금강판 관세 부과(확정) · 자료에 '適当'(부과가 적당) · 기간 5년 · 본문 출입처 포스코·KG스틸", ev[0]["text"])
        self.assertIn("② 비스페놀A 관세 부과(확정) · 자료에 '適当'(부과가 적당) · 기간 5년 · 부과 대상에서 제외 LG화학(자료 '…を除く') / ③", ev[0]["text"])
        self.assertIn("③ 수산화칼륨 과세 기간 연장(일몰)", ev[0]["text"])
        self.assertEqual(doc["status"], "ok")
        self.assertEqual(doc["checks"][-1]["source"], "일본 재무성 특수관세부회 배포자료")
        doc2, _ = run(page(L_PROV), extra=extra, prev=doc)
        self.assertEqual(doc2["fresh"], 0)
        self.assertEqual(len([e for e in doc2["events"] if e["id"].startswith("jpcouncil:")]), 1)
        self.assertNotIn("updatedAt", doc2["events"][-1])

    def test_pdf_failure_then_filled(self):
        extra = {w.COUNCIL_INDEX: council_index("2026-11-20"), C + "kanb20261120.html": MEETING}
        doc, _ = run(page(L_PROV), {"ka20260804": D_PROV}, extra=extra)
        ev = next(e for e in doc["events"] if e["id"] == "jpcouncil:20261120")
        self.assertIn("PDF 못 읽음(HTTP 404)", ev["text"])
        self.assertEqual(doc["status"], "partial")
        extra.update({C + "20261120/kanb20261120siryo2-2.pdf": PDF_GALV, C + "20261120/kanb20261120siryo3-2.pdf": PDF_BPA,
                      C + "20261120/kanb20261120siryo4-2.pdf": PDF_KOH})
        # 읽기 실패한 PDF는 read=False로 남아 다음 실행에 다시 읽는다
        doc2, _ = run(page(L_PROV), extra=extra, prev=doc)
        ev2 = next(e for e in doc2["events"] if e["id"] == "jpcouncil:20261120")
        self.assertNotIn("PDF 못 읽음", ev2["text"])
        self.assertIn("updatedAt", ev2)
        self.assertEqual(ev2["detectedAt"], ev["detectedAt"])

    def test_council_list_failure_is_partial_not_zero(self):
        doc, _ = run(page(L_PROV), {"ka20260804": D_PROV}, fail=(w.COUNCIL_INDEX,))
        self.assertEqual(doc["status"], "partial")
        self.assertEqual(doc["checks"][-1]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
