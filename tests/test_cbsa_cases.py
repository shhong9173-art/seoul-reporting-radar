"""캐나다 CBSA 사건 문서·시행 중 조치: 목록 파서(탐침 236~239에서 본 HTML 꼴), 기준선, 새 문서·상태 바뀜·새 사건, 조치 쪽 수출자 표."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cbsa_cases as c  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 14, 21, 30, tzinfo=KST)
IE, ER, AR = (u for _, _, u in c.LISTS)


def doc_row(href, title, day, plain_date=False):
    d = dt.date.fromisoformat(day)
    cell = day if plain_date else f'<time class="nowrap" datetime="{day}">{d.strftime("%d-%b-%Y")}</time>'
    return f'<tr> <td><a href="{href}">{title}</a></td> <td>{cell}</td> </tr>'


def case(title_html, rows):
    return ('<details class="box"> <summary> <h4>' + title_html + '</h4> </summary> <div> <table class="table table-bordered"> <thead> <tr class="active"> '
            '<th scope="col" class="col-md-9">Document</th> <th scope="col">Date issued/updated</th> </tr> </thead> <tbody> ' + "".join(rows) + " </tbody> </table> </div> </details>")


def page(cases):
    return "<html><body><main><h1>List</h1><h3>2026</h3>" + "".join(cases) + "</main></body></html>"


# 탐침 239: 행정재심 목록의 한국 사건(제목·문서 줄·주소 꼴 그대로)
LINE_PIPE = case('Carbon and alloy steel line pipe&nbsp;2: <span class="noBold">Dumping (South Korea)&mdash;Concludes on <time class="nowrap" datetime="2026-12-14">December 14, 2026</time></span>',
                 [doc_row("/sima-lmsi/ar-ra/lp22026/lp2202601-ni-eng.html", "Notice of initiation of administrative review", "2026-06-26"),
                  doc_row("/sima-lmsi/ar-ra/lp22026/lp2202601-se-eng.html", "Administrative review schedule", "2026-10-06"),
                  doc_row("https://ace-dedac.cbsa-asfc.cloud-nuage.canada.ca/ex?lang=en_CA&amp;proceedingId=LP2%202026%20UP1", "Exhibit list", "2026-06-26"),
                  doc_row("/sima-lmsi/ar-ra/lp22026/lp2202601-lc-eng.html", "Listing of counsel granted disclosure", "2026-09-01"),
                  doc_row("/sima-lmsi/ar-ra/lp22026/lp2202601-ne-eng.html", "Notice of extension of an administrative review", "2026-10-06")])
# 머리 안의 주석(탐침 239: 'Concludes on ( TBD ) <!-- August 21, 2026 -->')
COPPER = case('Copper pipe fittings: <span class="noBold">Dumping (China, South Korea and United States) and subsidy (China)&mdash;Concludes on ( TBD ) <!-- <time datetime="2026-08-21">August 21, 2026</time> --></span>',
              [doc_row("/sima-lmsi/ar-ra/cpf2026/cpf202601-ni-eng.html", "Notice of initiation of administrative review", "2026-06-01")])
OTHER = case('Concrete reinforcing bar&nbsp;2: <span class="noBold">Dumping (Portugal)&mdash;Concludes on <time datetime="2027-01-25">January 25, 2027</time></span>',
             [doc_row("/sima-lmsi/ar-ra/rb22026/rb2202601-ni-eng.html", "Notice of initiation of administrative review", "2026-07-30")])
# 옛 줄: 날짜가 글자, 'Concluded on 2021-01-07'
OLD = case("Heavy plate: Dumping (Chinese Taipei, Germany, South Korea, Malaysia, and Turkey) - Concluded on 2021-01-07",
           [doc_row("/sima-lmsi/i-e/hp2020/hp2020-ni-eng.html", "Notice of initiation of investigation", "2020-05-29", plain_date=True),
            doc_row("/sima-lmsi/i-e/hp2020/hp2020-fd-eng.html", "Statement of Reasons—final determination", "2021-01-22", plain_date=True)])
# 탐침 237: 종료재심 목록의 소형 변압기(2026-10-02 개시)
SPT = case('Small Power Transformers: <span class="noBold">Dumping (Chinese Taipei and South Korea)&mdash;Concludes on <time datetime="2027-02-26">February 26, 2027</time></span>',
           [doc_row("/sima-lmsi/er-rre/spt2026/spt2026-ni-eng.html", "Notice of initiation of expiry review investigation", "2026-10-02"),
            doc_row("/sima-lmsi/er-rre/spt2026/spt2026-se-eng.html", "Expiry review investigation schedule", "2026-10-02")])

MIF_MENU = ('<main><table><thead><tr><th>MIF code</th><th>Product</th><th>Type</th><th>Country</th><th>Tariff classification numbers</th></tr></thead><tbody>'
            '<tr> <td>TR</td> <td><a href="/sima-lmsi/mif-mev/tr-eng.html">Large power transformers</a></td> <td>Dumping</td> <td>South&nbsp;Korea</td> <td>8504.23.00.00</td> </tr>'
            '<tr> <td>CRS</td> <td><a href="/sima-lmsi/mif-mev/crs-eng.html">Cold-rolled steel</a></td> <td>Subsidy</td> <td>South&nbsp;Korea</td> <td>7209</td> </tr>'
            '<tr> <td>CRS</td> <td><a href="/sima-lmsi/mif-mev/crs-eng.html">Cold-rolled steel</a></td> <td>Dumping</td> <td>South&nbsp;Korea</td> <td>7209</td> </tr>'
            '<tr> <td>LP1</td> <td><a href="/sima-lmsi/mif-mev/lp1-eng.html">Line pipe 1</a></td> <td>Dumping</td> <td>China</td> <td>7304</td> </tr></tbody></table></main>')
TR_URL = "https://www.cbsa-asfc.gc.ca/sima-lmsi/mif-mev/tr-eng.html"
CRS_URL = "https://www.cbsa-asfc.gc.ca/sima-lmsi/mif-mev/crs-eng.html"


def tr_page(extra_action="", exporters=None):
    # 탐침 239: 대형 변압기 조치 쪽 — '조사 정보' 표와 수출자 표(나라 칸 없음, 바로 앞 h3가 나라)
    ex = exporters or [("HD Hyundai Electric Co., Ltd.", "709294128RM0002", "2014-03", "2025-07"), ("Hyosung Heavy Industries", "726675713RM0002", "2014-03", "2017-07"),
                       ("Iljin Electric Co., Ltd.", "806119897RM0002", "2026-08", "2026-08")]
    return ('<main><h2>Investigation information</h2> <p>The dates of the proceedings concerning this case are:</p> <table class="table table-bordered"> <thead> <tr class="active"> <th scope="col">Action</th> <th scope="col">Date</th> </tr> </thead> <tbody> '
            '<tr> <td><a href="/sima-lmsi/i-e/ad1395/ad1395-i12-de-eng.html">Initiation of Investigation</a></td> <td>April 23, 2012</td> </tr> '
            '<tr> <td><a href="/sima-lmsi/ar-ra/slpt2024/slpt202401-nc-eng.html">Administrative Review: HD Hyundai Electric Co., Ltd.</a></td> <td><time class="nowrap" datetime="2025-07-21">July 21, 2025</time></td> </tr> '
            + extra_action + '</tbody> </table> <h2>Duty liability ( Anti-dumping duties)</h2> <h3>Country of origin or export: South Korea</h3> <table><thead><tr><th>Exporter</th><th>Exporter ID</th><th>Cooperative since</th><th>Last revised</th></tr></thead><tbody>'
            + "".join(f"<tr><td>{n}</td><td>{i}</td><td>{s}</td><td>{r}</td></tr>" for n, i, s, r in ex) + "</tbody></table></main>")


# 탐침 239: 소형 변압기 조치 쪽 — 나라 칸이 있고 한국 칸이 두 줄에 걸친다
SPT_TABLE = ('<main><h2>Investigation information</h2><table><thead><tr><th>Action</th><th>Date</th></tr></thead><tbody><tr><td><a href="/sima-lmsi/i-e/spt2021/spt2021-in-eng.html">Initiation of investigation</a></td>'
             '<td><time datetime="2021-04-15">April 15, 2021</time></td></tr></tbody></table><h3>Country of origin or export: Chinese Taipei, and South Korea</h3>'
             '<table><thead><tr><th>Country</th><th>Exporter</th><th>Exporter ID</th><th>Cooperative since</th><th>Last revised</th></tr></thead><tbody>'
             '<tr><td>Chinese Taipei</td><td>Shihlin Electric &amp; Engineering Corporation</td><td>814909537RM0002</td><td>2021-11</td><td>2026-08</td></tr>'
             '<tr><td rowspan="2">South Korea</td><td>HD Hyundai Electric Co., Ltd.</td><td>709294128RM0002</td><td>2021-11</td><td>2025-07</td></tr>'
             '<tr><td>ILJIN Electric Co., Ltd.</td><td>806119897RM0002</td><td>2021-11</td><td>2026-08</td></tr></tbody></table></main>')


class Resp:
    def __init__(self, text="", status=200):
        self.text, self.status_code = text, status


class Site:
    def __init__(self, pages, down=()):
        self.pages, self.down, self.calls = pages, set(down), []

    def get(self, url, headers=None, timeout=None):
        self.calls.append(url)
        if url in self.down:
            return Resp(status=503)
        return Resp(self.pages.get(url, "<main></main>"))


def site(**over):
    pages = {IE: page([OLD]), ER: page([SPT]), AR: page([LINE_PIPE, COPPER, OTHER]), c.MIF_MENU: MIF_MENU, TR_URL: tr_page(), CRS_URL: tr_page()}
    pages.update(over.pop("pages", {}))
    return Site(pages, **over)


def run(prev, s, now=NOW):
    return c.collect(prev, now, get=s.get, sleep=lambda x: None)


class Parse(unittest.TestCase):
    def test_list_cases_dates_and_keys(self):
        cases, total = c.parse_list(page([LINE_PIPE, COPPER, OTHER]), "ar-ra", AR)
        self.assertEqual((total, [x["key"] for x in cases]), (3, ["ar-ra/lp22026/lp2202601", "ar-ra/cpf2026/cpf202601"]))          # 포르투갈 사건은 뺀다
        lp = cases[0]
        self.assertEqual((lp["title"], lp["state"], lp["stateDate"]), ("Carbon and alloy steel line pipe 2: Dumping (South Korea)—Concludes on December 14, 2026", "Concludes", "2026-12-14"))
        self.assertEqual([(d["key"], d["date"]) for d in lp["docs"]], [("lp2202601-ni", "2026-06-26"), ("lp2202601-se", "2026-10-06"), ("exhibit-list", "2026-06-26"),
                                                                       ("lp2202601-lc", "2026-09-01"), ("lp2202601-ne", "2026-10-06")])
        self.assertEqual(lp["docs"][0]["url"], "https://www.cbsa-asfc.gc.ca/sima-lmsi/ar-ra/lp22026/lp2202601-ni-eng.html")
        self.assertEqual((cases[1]["state"], cases[1]["stateDate"]), ("Concludes", ""))                                            # '( TBD )' — 주석 속 날짜는 읽지 않는다
        self.assertNotIn("August 21", cases[1]["title"])
        old, _ = c.parse_list(page([OLD]), "i-e", IE)
        self.assertEqual((old[0]["state"], old[0]["stateDate"], old[0]["docs"][1]["date"], old[0]["key"]), ("Concluded", "2021-01-07", "2021-01-22", "i-e/hp2020/hp2020"))
        self.assertEqual([c.iso_date(x) for x in ("11-Aug-2025", "2020-Mar-20", "December 14, 2026", "2021-04-15", "TBD")], ["2025-08-11", "2020-03-20", "2026-12-14", "2021-04-15", ""])

    def test_measure_pages(self):
        menu = c.parse_mif_menu(MIF_MENU)
        self.assertEqual([(m["code"], m["type"], m["url"]) for m in menu], [("TR", "Dumping", TR_URL), ("CRS", "Subsidy·Dumping", CRS_URL)])   # 같은 쪽은 한 번, 중국 줄은 뺀다
        actions, exporters = c.parse_measure(tr_page(), TR_URL)
        self.assertEqual([(a["title"], a["date"]) for a in actions], [("Initiation of Investigation", "2012-04-23"), ("Administrative Review: HD Hyundai Electric Co., Ltd.", "2025-07-21")])
        self.assertEqual([(x["name"], x["since"], x["revised"]) for x in exporters][2], ("Iljin Electric Co., Ltd.", "2026-08", "2026-08"))
        _, spt = c.parse_measure(SPT_TABLE, TR_URL)
        self.assertEqual([x["name"] for x in spt], ["HD Hyundai Electric Co., Ltd.", "ILJIN Electric Co., Ltd."])                 # 대만 줄은 빼고, 나라 칸이 걸친 둘째 줄도 한국


class Collect(unittest.TestCase):
    def test_first_run_is_baseline_and_counts(self):
        sec, events, check = run(None, site())
        self.assertEqual(events, [])
        self.assertEqual((check["status"], check["cases"], check["open"], check["measures"], check["exporters"]), ("ok", 4, 3, 2, 6))
        lp = sec["lists"]["ar-ra"]["cases"]["ar-ra/lp22026/lp2202601"]
        self.assertEqual((lp["state"], lp["stateDate"], lp["n"], lp["latest"], len(lp["docs"])), ("Concludes", "2026-12-14", 5, "2026-10-06", 5))
        self.assertNotIn("docs", sec["lists"]["i-e"]["cases"]["i-e/hp2020/hp2020"])                                               # 오래 전 끝난 사건은 열쇠만
        self.assertEqual(sec["measures"][TR_URL]["companies"], ["HD현대일렉트릭", "일진전기(관련)", "효성중공업(관련)"])

    def test_new_document_state_change_and_new_case(self):
        prev, _, _ = run(None, site())
        ended = LINE_PIPE.replace("Concludes on", "Concluded on").replace("</tbody>", doc_row("/sima-lmsi/ar-ra/lp22026/lp2202601-nc-eng.html", "Notice of conclusion of administrative review", "2026-12-14")
                                                                           + doc_row("/sima-lmsi/ar-ra/lp22026/lp2202601-su-eng.html", "Updated schedule", "2026-12-01")
                                                                           + doc_row("/sima-lmsi/ar-ra/lp22026/lp2202601-ex-eng.html", "Exhibit list (updated)", "2026-12-14") + "</tbody>")
        new_er = case('Oil Country Tubular Goods&nbsp;2: <span class="noBold">Dumping (South Korea)&mdash;Concludes on <time datetime="2027-05-01">May 1, 2027</time></span>',
                      [doc_row("/sima-lmsi/er-rre/octg22026/octg22026-ni-eng.html", "Notice of initiation of expiry review investigation", "2026-12-10")])
        new_ie = case("Steel widgets: Dumping (South Korea)—Concludes on 2027-03-01", [doc_row("/sima-lmsi/i-e/sw2026/sw2026-ni-eng.html", "Notice of initiation of investigation", "2026-12-11", True)])
        s = site(pages={AR: page([ended, COPPER, OTHER]), ER: page([SPT, new_er]), IE: page([OLD, new_ie])})
        sec, events, check = run(prev, s, NOW + dt.timedelta(days=31))
        texts = {e["id"]: (e["tier"], e["text"]) for e in events}
        self.assertEqual(texts["cbsa:ar-ra/lp22026/lp2202601:lp2202601-nc"],
                         ("B", "Carbon and alloy steel line pipe 2: Dumping (South Korea)—Concluded on December 14, 2026 — 새 문서 「Notice of conclusion of administrative review」(2026-12-14)"))
        self.assertEqual(texts["cbsa:ar-ra/lp22026/lp2202601:lp2202601-su"][0], "C")                                            # 일정 문서는 C
        self.assertFalse(any("Exhibit list" in t for _, t in texts.values()))                                                  # 증거 목록은 알리지 않는다
        self.assertIn("사건 머리 바뀜: Concludes 2026-12-14 → Concluded 2026-12-14", texts["cbsa:ar-ra/lp22026/lp2202601:state:Concluded:2026-12-14"][1])
        self.assertEqual(texts["cbsa:er-rre/octg22026/octg22026"], ("B", "새 사건 — Oil Country Tubular Goods 2: Dumping (South Korea)—Concludes on May 1, 2027 · 문서 1건(「Notice of initiation of expiry review investigation」 2026-12-10)"))
        self.assertFalse(any(e["id"].startswith("cbsa:i-e/sw2026") for e in events))                                            # '조사' 목록의 새 사건은 기존 목록 줄 감시가 낸다
        self.assertEqual((check["newDocs"], check["stateChanges"], check["newCases"], len(events)), (2, 1, 1, 4))
        self.assertTrue(all(e["pageId"] == "cbsa" and e["country"] == "캐나다" and e["url"].startswith("https://www.cbsa-asfc.gc.ca/") for e in events))
        # 다음 실행: 같은 것을 다시 알리지 않는다
        _, again, _ = run(sec, s, NOW + dt.timedelta(days=32))
        self.assertEqual(again, [])

    def test_measure_page_changes_name_beat_exporters(self):
        prev, _, _ = run(None, site())
        action = '<tr> <td><a href="/sima-lmsi/ar-ra/slpt2026/slpt202601-nc-eng.html">Administrative Review</a></td> <td><time datetime="2026-08-14">August 14, 2026</time></td> </tr> '
        ex = [("HD Hyundai Electric Co., Ltd.", "709294128RM0002", "2014-03", "2026-12"), ("Iljin Electric Co., Ltd.", "806119897RM0002", "2026-08", "2026-08"),
              ("LS Electric Co., Ltd.", "111111111RM0001", "2026-12", "2026-12"), ("Small Maker Co.", "2", "2014-03", "2017-07")]
        prev["measures"][TR_URL]["exporters"].append({"name": "Small Maker Co.", "since": "2014-03", "revised": "2016-01", "country": "South Korea"})
        sec, events, check = run(prev, site(pages={TR_URL: tr_page(action, ex)}), NOW + dt.timedelta(days=40))
        got = {e["text"]: (e["tier"], e.get("companies")) for e in events}
        self.assertEqual(got["조치 쪽에 새 절차 줄 「Administrative Review」(2026-08-14)"], ("B", None))
        self.assertEqual(got["한국 수출자 「HD Hyundai Electric Co., Ltd.」의 정상가격 마지막 개정 2025-07 → 2026-12"], ("B", ["HD현대일렉트릭"]))
        self.assertEqual(got["정상가격을 받은 한국 수출자에 새 이름 「LS Electric Co., Ltd.」(협조 시작 2026-12 · 마지막 개정 2026-12)"], ("B", ["LS일렉트릭"]))
        self.assertEqual(got["정상가격을 받은 한국 수출자 표에서 「Hyosung Heavy Industries」이 빠짐"], ("B", ["효성중공업(관련)"]))
        self.assertEqual(got["한국 수출자 「Small Maker Co.」의 정상가격 마지막 개정 2016-01 → 2017-07"], ("C", None))               # 출입처가 아닌 곳의 개정은 C
        self.assertTrue(all(e["label"] == "캐나다 CBSA 시행 중 조치 TR(Large power transformers)" for e in events))
        self.assertEqual(len(events), 5)

    def test_old_style_addresses_get_unique_keys_and_key_changes_are_quiet(self):
        # 탐침 240: 옛 재조사는 주소 꼴이 달라 제목으로 열쇠를 만들었고, 같은 품목의 해마다 다른 재조사가 한 열쇠로 겹쳤다(읽은 94건 → 저장 85건)
        old15 = case("Copper pipe fittings: Dumping (China, Korea, and United-States); Countervailing (China) - Concluded on 2015-11-25",
                     [doc_row("/sima-lmsi/ri-re/ad1358/ad1358-ri15-nc-eng.html", "Notice of conclusion of re-investigation", "2015-11-25", True)])
        old14 = case("Copper pipe fittings: Dumping (China, Korea, and United-States); Countervailing (China) - Concluded on 2014-10-20",
                     [doc_row("/sima-lmsi/ri-re/ad1358/ad1358-ri14-nc-eng.html", "Notice of conclusion of re-investigation", "2014-10-20", True)])
        wire = case("Stainless steel wire: Dumping (Korea, Switzerland and United-States) - Concluded on 2008-05-01", [doc_row("/sima-lmsi/ri-re/ad1292/ad1292nc-eng.html", "Notice of conclusion", "2008-05-01", True)])
        cases, _ = c.parse_list(page([old15, old14, wire]), "ar-ra", AR)
        self.assertEqual([x["key"] for x in cases], ["ar-ra/ad1358/ad1358-ri15-nc", "ar-ra/ad1358/ad1358-ri14-nc", "ar-ra/ad1292/ad1292nc"])
        # 직전 저장분이 옛 열쇠(제목)로 돼 있어도 새 사건·새 문서로 알리지 않는다
        s = site(pages={AR: page([LINE_PIPE, old15, old14])})
        prev, _, _ = run(None, s)
        cs = prev["lists"]["ar-ra"]["cases"]
        cs["ar-ra/copper-pipe-fittings-old-title-key"] = {**cs.pop("ar-ra/ad1358/ad1358-ri15-nc"), "seen": []}
        cs["ar-ra/another-old-key"] = {**cs.pop("ar-ra/ad1358/ad1358-ri14-nc"), "seen": []}
        sec, events, check = run(prev, s, NOW + dt.timedelta(days=1))
        self.assertEqual((events, check["newCases"], check["newDocs"]), ([], 0, 0))
        self.assertEqual(sorted(sec["lists"]["ar-ra"]["cases"]), ["ar-ra/ad1358/ad1358-ri14-nc", "ar-ra/ad1358/ad1358-ri15-nc", "ar-ra/lp22026/lp2202601"])
        self.assertTrue(sec["lists"]["ar-ra"]["cases"]["ar-ra/ad1358/ad1358-ri15-nc"]["seen"])                                      # 문서 열쇠도 이어받는다

    def test_old_cases_and_old_documents_are_never_news(self):
        # 11-14 운영: 열쇠가 겹쳐 저장되지 않았던 2008~2016년 재조사 9건이 '새 사건'으로 나갔다 — 오래전 끝난 사건은 알리지 않는다
        prev, _, _ = run(None, site())
        old = case("Copper pipe fittings: Dumping (China, Korea, and United-States) - Concluded on 2015-11-25",
                   [doc_row("/sima-lmsi/ri-re/ad1358/ad1358-ri15-nc-eng.html", "(Archived) - Notice of Conclusion of Re-investigation", "2015-11-25", True)])
        relinked = LINE_PIPE.replace("</tbody>", doc_row("/sima-lmsi/ar-ra/lp22026/lp2202601-zz-eng.html", "(Archived) - Old notice", "2019-01-01", True) + "</tbody>")
        sec, events, check = run(prev, site(pages={AR: page([relinked, COPPER, OTHER, old])}), NOW + dt.timedelta(days=1))
        self.assertEqual((events, check["newCases"], check["newDocs"]), ([], 0, 0))
        self.assertIn("ar-ra/ad1358/ad1358-ri15-nc", sec["lists"]["ar-ra"]["cases"])                                             # 저장은 한다
        # 이미 나간 잘못된 것은 표시만 하고 지우지 않는다(11-14 운영에서 나간 꼴 그대로). 최근 날짜의 것·다른 원천은 그대로
        at = "2026-11-14T15:58:00+09:00"
        stored = [{"id": "cbsa:ar-ra/copper-old:ri15-nc", "pageId": "cbsa", "detectedAt": at, "text": "Copper pipe fittings: Dumping (China, Korea, and United-States) - Concluded on 2016-02-05 — 새 문서 「(Archived) - Notice of Conclusion of Re-investigation」(2016-02-05)"},
                  {"id": "cbsa:ar-ra/copper-old:state:Concluded:2016-02-05", "pageId": "cbsa", "detectedAt": at, "text": "Copper pipe fittings … - Concluded on 2016-02-05 — 사건 머리 바뀜: Concluded 2007-07-16 → Concluded 2016-02-05"},
                  {"id": "cbsa:ar-ra/ad1358/ad1358-ri15-nc", "pageId": "cbsa", "detectedAt": "2026-11-14T16:06:00+09:00", "text": "새 사건 — Copper pipe fittings: Dumping (China, Korea, and United-States) - Concluded on 2016-02-05 · 문서 2건(「(Archived) - Notice」 2016-02-05)"},
                  {"id": "cbsa:ar-ra/lp22026/lp2202601:lp2202601-nc", "pageId": "cbsa", "detectedAt": "2026-12-15T07:40:00+09:00", "text": "Carbon and alloy steel line pipe 2 … — 새 문서 「Notice of conclusion of administrative review」(2026-12-14)"},
                  {"id": "cbsa:ar-ra/lp22026/lp2202601:state:Concluded:2026-12-14", "pageId": "cbsa", "detectedAt": "2026-12-15T07:40:00+09:00", "text": "Carbon … — 사건 머리 바뀜: Concludes 2026-12-14 → Concluded 2026-12-14"},
                  {"id": "cbsa:er-rre/octg22026/octg22026", "pageId": "cbsa", "detectedAt": "2026-12-15T07:40:00+09:00", "text": "새 사건 — Oil Country Tubular Goods 2: Dumping (South Korea)—Concludes on May 1, 2027 · 문서 1건"},
                  {"id": "cbsa:mif:TR:rev:x", "pageId": "cbsa", "detectedAt": at, "text": "한국 수출자 「HD Hyundai Electric Co., Ltd.」의 정상가격 마지막 개정 2025-07 → 2026-12"},
                  {"id": "in-dgtr:x", "pageId": "in-dgtr", "detectedAt": at, "text": "x — 새 문서 「y」(2010-01-01)"}]
        self.assertEqual(c.retract_stale(stored, sec, NOW + dt.timedelta(days=40)), 3)
        self.assertEqual([bool(e.get("retracted")) for e in stored], [True, True, True, False, False, False, False, False])
        self.assertEqual(c.retract_stale(stored, sec, NOW + dt.timedelta(days=41)), 0)                                             # 다시 세지 않는다
        # 옛 사건의 머리가 달라 보여도(겹친 열쇠) 상태 바뀜으로 알리지 않는다
        prev2, _, _ = run(None, site(pages={AR: page([LINE_PIPE, old])}))
        key = "ar-ra/ad1358/ad1358-ri15-nc"
        prev2["lists"]["ar-ra"]["cases"][key]["stateDate"] = "2007-07-16"
        _, ev2, chk2 = run(prev2, site(pages={AR: page([LINE_PIPE, old])}), NOW + dt.timedelta(days=1))
        self.assertEqual((ev2, chk2["stateChanges"]), ([], 0))

    def test_affiliate_names_are_not_beat_companies(self):
        self.assertEqual(c.beat_in("Hyundai Steel Pipe Co., Ltd."), [])                                                            # 현대스틸파이프는 현대제철이 아니다
        self.assertEqual(c.beat_in("Hyundai Steel Company"), ["현대제철"])
        self.assertEqual(c.beat_in("Hyundai Steel Company; Hyundai Steel Pipe Co., Ltd."), ["현대제철"])

    def test_failures_keep_the_previous_state(self):
        prev, _, _ = run(None, site())
        sec, events, check = run(prev, site(down=[AR, TR_URL]), NOW + dt.timedelta(days=1))
        self.assertEqual((check["status"], events), ("partial", []))
        self.assertIn("행정재심 HTTP 503", check["error"])
        self.assertEqual((sec["lists"]["ar-ra"]["status"], len(sec["lists"]["ar-ra"]["cases"])), ("failed", 2))                   # 직전 사건 그대로
        self.assertTrue(sec["measures"][TR_URL]["stale"])
        # 다시 열리면 그사이 붙은 문서를 알린다(실패한 실행이 기준선을 지우지 않았다)
        later = LINE_PIPE.replace("</tbody>", doc_row("/sima-lmsi/ar-ra/lp22026/lp2202601-nc-eng.html", "Notice of conclusion of administrative review", "2026-12-14") + "</tbody>")
        _, events2, _ = run(sec, site(pages={AR: page([later, COPPER, OTHER])}), NOW + dt.timedelta(days=2))
        self.assertEqual([e["id"] for e in events2], ["cbsa:ar-ra/lp22026/lp2202601:lp2202601-nc"])
        # 형식이 바뀌어 사건 줄이 안 보이면 실패(0건으로 넘기지 않는다)
        _, _, check3 = run(prev, site(pages={ER: "<main><p>maintenance</p></main>"}), NOW + dt.timedelta(days=1))
        self.assertIn("종료재심 사건 줄 없음(형식 변경 의심)", check3["error"])
        _, _, all_down = run(None, site(down=[IE, ER, AR, c.MIF_MENU]))
        self.assertEqual(all_down["status"], "failed")


if __name__ == "__main__":
    unittest.main()
