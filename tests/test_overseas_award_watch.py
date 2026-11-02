"""해외 발주처 낙찰 감시: TED 낙찰자 필드, 영국 FTS 공급사, 세계은행 'Awarded Bidder' 칸만, 바레인 월간 보고서·개찰 결과, 기준선·새 항목·실패 보존."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import overseas_award_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 29, 17, 30, tzinfo=KST)


class Resp:
    def __init__(self, body=None, status=200, text=None, content=None):
        self._body, self.status_code = body, status
        self.text = text if text is not None else json.dumps(body or {})
        self.content = content if content is not None else self.text.encode()

    def json(self):
        return self._body


TED_HYOSUNG = {"publication-number": "545946-2026", "publication-date": "2026-08-06+02:00", "notice-type": "can-standard",
               "buyer-name": {"eng": ["Energinet Eltransmission A/S"]}, "buyer-country": ["DNK"],
               "winner-name": {"eng": ["Hyosung Heavy Industires Corporation"]}, "winner-country": ["KOR"], "winner-identifier": ["578-87-00896"],
               "title-lot": {"eng": ["400/220 kV Autotransformers for SLF02"]}, "result-value-notice": "15923696", "result-value-cur-notice": "EUR",
               "contract-conclusion-date": ["2026-06-19Z"]}
TED_FRAMEWORK = {"publication-number": "558812-2026", "publication-date": "2026-08-12+02:00", "notice-type": "can-standard",
                 "buyer-name": {"eng": ["Ellevio AB"]}, "buyer-country": ["SWE"], "winner-name": {"eng": ["HD Hyundai Electric Co., Ltd."]},
                 "winner-country": ["KOR"], "total-value": 1, "total-value-cur": ["SEK"]}
TED_SUBSIDIARY = {"publication-number": "546637-2026", "publication-date": "2026-08-06+02:00", "notice-type": "can-modif",
                  "buyer-name": {"eng": ["Energinet Eltransmission A/S"]}, "buyer-country": ["DNK"],
                  "winner-name": {"eng": ["HD Hyundai Electric Europe GmbH"]}, "winner-country": ["DEU"], "total-value": 31169665, "total-value-cur": ["EUR"]}
TED_OTHER_KR = {"publication-number": "721359-2026", "publication-date": "2026-10-20+02:00", "notice-type": "can-standard",
                "buyer-name": {"pol": ["Enea Elektrownia Połaniec sp. z o.o."]}, "buyer-country": ["POL"],
                "winner-name": {"pol": ["Nano Co., Ltd."]}, "winner-country": ["KOR"]}
TED_NOT_KR = {"publication-number": "65790-2026", "publication-date": "2026-01-29+01:00", "notice-type": "can-standard",
              "buyer-name": {"spa": ["REE"]}, "winner-name": {"spa": ["EFACEC Energia"]}, "winner-country": ["PRT"]}

WB_AWARD = {"id": "OP00477000", "noticedate": "20-Oct-2026", "notice_type": "Contract Award", "project_ctry_name": "Iraq",
            "project_name": "Electricity Sector Reconnection", "bid_description": "Supply of 400 kV power transformers",
            "notice_text": ("<p>Duration of Contract: 12 Month(s)</p><p>Awarded Bidder(s): HYOSUNG HEAVY INDUSTRIES CORPORATION (496851) 119, Mapo-daero, "
                            "Mapo-gu, Seoul, Korea Country: Korea, Republic of Bid Price at Opening USD 38,500,000.00 Evaluated Bid Price USD 38,410,000.00</p>"
                            "<p>Evaluated Bidder(s): SIEMENS ENERGY (12345) Country: Germany</p>")}
WB_REJECTED = {"id": "OP00305046", "noticedate": "18-Oct-2026", "notice_type": "Contract Award", "project_ctry_name": "Ukraine",
               "project_name": "Winterization", "bid_description": "Autotransformers 330 kV",
               "notice_text": ("<p>Awarded Bidder(s): KYIV ENERGY CONSTRUCTION COMPANY (776840) Country: Ukraine Bid Price at Opening UAH 1,000,000.00</p>"
                               "<p>Rejected Bidder(s): Reason for Rejection Non Responsive HYOSUNG HEAVY INDUSTRIES CORPORATION (496851) Country: Korea, Republic of</p>")}
WB_OLD = dict(WB_AWARD, id="OP00100000", noticedate="03-Nov-2022")

FTS_REL = {"id": "102400-2026", "ocid": "ocds-h6vhtk-0aaaaa", "date": "2026-10-28T10:00:00Z", "tag": ["award", "contract"],
           "buyer": {"id": "GB-NG", "name": "National Grid Electricity Transmission plc"},
           "tender": {"title": "HVDC cable supply - Eastern Green Link 3"},
           "parties": [{"id": "GB-NG", "name": "National Grid Electricity Transmission plc", "roles": ["buyer"], "address": {"countryName": "United Kingdom"}},
                       {"id": "S1", "name": "LS CABLE & SYSTEM UK LIMITED", "roles": ["supplier"], "address": {"countryName": "United Kingdom"}},
                       {"id": "S2", "name": "Some Korean Engineering Co", "roles": ["supplier"], "address": {"countryName": "Korea, Republic of"}}],
           "awards": [{"id": "102400-2026-1", "suppliers": [{"id": "S1", "name": "LS CABLE & SYSTEM UK LIMITED"}], "value": {"amount": 250000000, "currency": "GBP"}}]}
FTS_UK_ONLY = {"id": "102401-2026", "date": "2026-10-28T11:00:00Z", "tender": {"title": "Software"}, "parties": [
    {"id": "X", "name": "Acme Ltd", "roles": ["supplier"], "address": {"countryName": "United Kingdom"}}], "awards": []}

BH_HTML = ('<table><tr><th>No</th><th>Subject</th></tr>'
           '<tr><td>1</td><td>Awarded Tenders Report - September 2026</td><td><a href="/MediaHandler/GenericHandler/Pdf/Awarded/Awarded Tenders 2026-09.pdf">PDF</a></td></tr>'
           '<tr><td>2</td><td>Awarded Tenders Report - August 2026</td><td><a href="/MediaHandler/GenericHandler/Pdf/Awarded/Awarded Tenders 2026-08.pdf">PDF</a></td></tr></table>')


def pcc_rec(date, fn, typ, title, name_key, amount, job="0081520071", unit="3.13.31", buyer="台灣電力股份有限公司"):
    """10-30 탐침 모양(g0v 미러 searchbycompanyname 레코드)."""
    return {"date": date, "filename": fn, "brief": {"type": typ, "title": title, "companies": {"ids": [], "names": list(name_key), "id_key": {}, "name_key": name_key}},
            "job_number": job, "unit_id": unit, "unit_name": buyer, "award_amount": amount, "budget_amount": None,
            "url": f"/index/case/{unit}/{job}/{date}/{fn}", "tender_api_url": f"http://pcc-api.openfun.app/api/tender?unit_id={unit}&job_number={job}"}


PCC_LS = pcc_rec(20261028, "BDM-1-71300001", "決標公告", "115年度供電單位複合光纖地線暨附屬器材統購案",
                 {"LS Cable & System Ltd.": ["投標廠商:投標廠商1:廠商名稱", "決標品項:第2品項:得標廠商1:得標廠商"],
                  "中華電線電纜股份有限公司": ["投標廠商:投標廠商3:廠商名稱", "決標品項:第1品項:得標廠商1:得標廠商"],
                  "Tratos Cavi Germany GmbH": ["投標廠商:投標廠商2:廠商名稱", "決標品項:第2品項:未得標廠商1:未得標廠商"]}, 858849686)
PCC_LOSER = pcc_rec(20261027, "BDM-1-71300002", "決標公告", "161kV電纜", {"LS Cable & System Ltd.": ["決標品項:第1品項:未得標廠商1:未得標廠商"],
                                                                     "華新麗華股份有限公司": ["決標品項:第1品項:得標廠商1:得標廠商"]}, 5000000, job="X2")
PCC_LSE = pcc_rec(20261020, "BDM-2-71290000", "更正決標公告", "臺鐵號誌電子聯鎖系統工程第2次契約變更",
                  {"韓商樂星電氣股份有限公司臺灣分公司": ["投標廠商:投標廠商1:廠商名稱", "決標品項:第1品項:得標廠商1:得標廠商"]}, 38204450,
                  job="SJ01-CCO-02", unit="A.15.5.1", buyer="交通部鐵道局北部工程分局")
PCC_FIBER = pcc_rec(20261015, "BDM-1-71280000", "決標公告", "鋁包鋼線一批", {"TAIHAN FIBEROPTICS CO., LTD.": ["決標品項:第1品項:得標廠商1:得標廠商"]}, 17883620, job="X3")
PCC_OLD = pcc_rec(20250923, "BDM-1-70925493", "更正決標公告", "超耐熱鋼心鋁線", {"LS Cable & System Ltd.": ["決標品項:第2品項:得標廠商1:得標廠商"]}, 858849686, job="X4")
PCC_DETAIL = {"records": [{"filename": "TIQ-1-1", "detail": {}}, {"filename": "BDM-1-71300001", "detail": {
    "決標品項:第1品項:得標廠商1:得標廠商": "中華電線電纜股份有限公司", "決標品項:第1品項:得標廠商1:決標金額": "582,764,700元",
    "決標品項:第2品項:品項名稱": "超耐熱鋼心鋁線ZTACIR 260mm2", "決標品項:第2品項:得標廠商1:得標廠商": "LS Cable & System Ltd.",
    "決標品項:第2品項:得標廠商1:決標金額": "276,084,986元", "決標品項:第2品項:得標廠商1:原產地國別:原產地國別": "南韓(Republic of Korea)",
    "決標資料:決標日期": "115/10/24", "採購資料:標的分類": "<財物類>463絕緣電線,電纜及光纖電纜"}}]}


# 바레인 입찰위원회 개찰 결과(10-30 탐침에서 본 형식): 목록은 웹 메서드 응답 d 안 XML의 <Content>에 HTML이 엔터티로 들어 있다.
def bh_open_row(ref, no, subject, opened, authority, bids, envelope="PB"):
    href = f"/OpenedTenderDetails/?id={no.replace('/', '%2f')}&amp;source=New&amp;envelope={envelope}&amp;type=1"
    return (f"<div data-ref='{ref}' class='rows'><div class='column' data-label='#'>1</div><div class='column' data-label='Subject'>"
            f"<a href='{href}'><span>{no}</span>{subject}</a></div><div class='column' data-label='Type'>External</div>"
            f"<div class='column' data-label='Date'>{opened}</div><div class='column' data-label='Authority'>{authority}</div>"
            f"<div class='column' data-label='Bids'>{bids}</div></div>")


BH_OPEN_ROWS = [
    bh_open_row("9001", "4669/2025/5100", "400kV and 220kV Feeder Cable Works for Establishment of New Sitra 400kV Grid Substation",
                "13 Apr,2026", "Electricity and Water Authority (Planning)", 3),
    bh_open_row("9002", "SES-26/0015", "JETTING CLEANING OF SEWER AND STORM WATER SYSTEM", "29 Oct,2026", "Ministry of Works", 2),
    bh_open_row("9003", "PT/CSD/AS/2026/019", "Supply of 66KV Switchgear", "28 Oct,2026", "Central Stores Directorate - EWA", 2, envelope="TQ"),
]


def bh_open_page(rows):
    content = "".join(rows).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return {"d": f"<NewDataSet><Pager><PageIndex>1</PageIndex><PageSize>10</PageSize><RecordCount>9124</RecordCount>"
                 f"<Content>{content}</Content></Pager></NewDataSet>"}


def bidder(n, name, value_html, status="Accepted"):
    return (f"<div class='rows'><div class='column' data-label='#'>{n}</div><div class='column' data-label='Bidder Name'>{name}</div>"
            f"<div class='column bidvalue' data-label='Bidder Value'>{value_html}</div><div class='column' data-label='Remarks On Opened Bid'>"
            f"<div><p class='remarks'></p></div></div><div status='{status}' class='column' data-label='Status'>{status}</div></div>")


BH_DETAILS = {
    "9001": "<dl><dt>Issued by</dt><dd>EWA</dd></dl><div class='rows header'><div class='column'>Bidder Name</div></div>"
            + bidder(1, "TAIHAN ELECTRIC WIRE CO LTD", "<div>(Opt. 1) <span>BHD 45,648,300.000</span></div><div>(Opt. 2) <span>BHD 47,022,441.000</span></div>")
            + bidder(2, "LS CABLE AND SYSTEM LTD", "<span>BHD 46,659,985.550</span>")
            + bidder(3, "ILJIN ELECTRIC", "<span>BHD 35,004,118.330</span>"),
    "9002": bidder(1, "ALMOAYYED CONTRACTING W.L.L.", "<span>BHD 120,000.000</span>") + bidder(2, "GULF CLEANING CO", "<span>BHD 99,500.000</span>"),
    "9003": bidder(1, "LS ELECTRIC CO., LTD.", "<span></span>") + bidder(2, "HYOSUNG HEAVY INDUSTRIES CORPORATION", "<span></span>", "Rejected"),
}


def fakes(ted_rows=(TED_HYOSUNG, TED_FRAMEWORK, TED_SUBSIDIARY, TED_OTHER_KR, TED_NOT_KR), wb_rows=(WB_AWARD, WB_REJECTED, WB_OLD),
          fts_rels=(FTS_REL, FTS_UK_ONLY), bh_text="Tender 12/2026 EWA 400kV transformers HYOSUNG HEAVY INDUSTRIES BHD 4,200,000",
          pcc_rows=(PCC_LS, PCC_LOSER, PCC_LSE, PCC_FIBER, PCC_OLD), bh_open=tuple(BH_OPEN_ROWS)):
    calls = {"ted": 0, "wb": 0, "fts": 0, "bh_pdf": 0, "pcc": 0, "pcc_detail": 0, "bh_open": 0, "bh_open_detail": 0}

    def post(url, json=None, headers=None, timeout=None, data=None):
        if url == w.BH_OPEN_API:
            calls["bh_open"] += 1
            page = int(__import__("json").loads(data)["pageIndex"])
            return Resp(bh_open_page(list(bh_open) if page == 1 else []))
        calls["ted"] += 1
        return Resp({"notices": list(ted_rows), "totalNoticeCount": len(ted_rows)})

    def get(url, params=None, headers=None, timeout=None):
        if url.startswith(w.WB_API):
            calls["wb"] += 1
            return Resp({"procnotices": list(wb_rows), "total": len(wb_rows)})
        if url.startswith(w.FTS_API):
            calls["fts"] += 1
            return Resp({"releases": list(fts_rels), "links": {}})
        if url == w.BH_LIST:
            return Resp(text=BH_HTML)
        if url.startswith(w.BH_SITE + "/OpenedTenderDetails/"):
            calls["bh_open_detail"] += 1
            ref = {"4669": "9001", "SES-": "9002", "PT%2": "9003"}[url.split("id=")[1][:4]]
            return Resp(text=BH_DETAILS[ref])
        if url.endswith(".pdf"):
            calls["bh_pdf"] += 1
            return Resp(text="", content=b"%PDF")
        if url == w.PCC_SEARCH:
            calls["pcc"] += 1
            return Resp({"query": params["query"], "page": 1, "total_records": len(pcc_rows), "records": list(pcc_rows)})
        if url == w.PCC_TENDER:
            calls["pcc_detail"] += 1
            return Resp(PCC_DETAIL if params.get("job_number") == "0081520071" else {"records": []})
        raise AssertionError(url)
    return get, post, calls


class Award(unittest.TestCase):
    def setUp(self):
        self._pdf, self._ocr = w.pdf_text, w.ocr_pdf
        w.ocr_pdf = lambda raw: (None, "글자 인식 도구 없음")
        w.pdf_text = lambda raw: ("Awarded Tenders\nTender 12/2026 EWA 400kV transformers\nHYOSUNG HEAVY INDUSTRIES BHD 4,200,000\n"
                                  + "\n".join(f"Tender {i}/2026 Ministry of Works road maintenance ALMOAYYED W.L.L. BHD {i}00" for i in range(30)))

    def tearDown(self):
        w.pdf_text, w.ocr_pdf = self._pdf, self._ocr

    def test_ted_winner_fields_only(self):
        items = {x["id"]: x for x in w.ted_items([TED_HYOSUNG, TED_FRAMEWORK, TED_SUBSIDIARY, TED_OTHER_KR, TED_NOT_KR])}
        self.assertEqual(set(items), {"ted:545946-2026", "ted:558812-2026", "ted:546637-2026", "ted:721359-2026"})
        h = items["ted:545946-2026"]
        self.assertEqual((h["company"], h["value"], h["currency"], h["concluded"], h["buyerCountry"]), ("효성중공업", 15923696.0, "EUR", "2026-06-19", "DNK"))
        self.assertEqual(h["winnerIds"], ["578-87-00896"])
        self.assertIsNone(items["ted:558812-2026"]["value"])  # framework placeholder 1
        self.assertEqual(items["ted:546637-2026"]["kind"], "계약 변경")
        self.assertEqual(items["ted:546637-2026"]["company"], "HD현대일렉트릭")
        self.assertIsNone(items["ted:721359-2026"]["company"])  # Korean but not a beat company

    def test_names_tiers_and_scanned_pdf(self):
        self.assertEqual(w.beat_of("DE_HYOSUNG HEAVY INDUSTRIES CORPORATION"), "효성중공업")  # TED 국가 접두어
        self.assertIsNone(w.beat_of("Hanwha Aerospace Co., Ltd."))  # 방산은 출입처 밖
        local = dict(TED_HYOSUNG, **{"publication-number": "700001-2026", "winner-name": {"ces": ["Hyundai Motor Czech s.r.o."]}, "winner-country": ["CZE"]})
        hq = dict(TED_HYOSUNG, **{"publication-number": "700002-2026", "winner-name": {"eng": ["Hyundai Motor Company"]}, "winner-country": ["KOR"]})
        got = {x["id"]: w.tier_of(x) for x in w.ted_items([local, hq])}
        self.assertEqual(got, {"ted:700001-2026": "B", "ted:700002-2026": "A"})
        w.pdf_text = lambda raw: "   "
        get, post, _ = fakes()
        doc = w.run(now=NOW, previous=None, get=get, post=post, sleep=lambda s: None)
        bh = [c for c in doc["checks"] if c["source"] == "바레인 입찰위원회"]
        self.assertEqual((bh[0]["status"], bh[0]["matched"]), ("ok", None))
        self.assertIn("스캔 이미지", bh[0]["note"])
        self.assertIn("글자 인식 실패(글자 인식 도구 없음)", bh[0]["note"])
        self.assertIn("/MediaHandler/GenericHandler/Pdf/Awarded/Awarded Tenders 2026-09.pdf", doc["bahrainSeen"])  # not retried

    def test_scanned_report_read_by_ocr(self):
        # 11-02 탐침: 바레인 8월 보고서(스캔 이미지) 200dpi 글자 인식 줄 그대로 — 이름 띄어쓰기가 사라지고 아랍어 칸은 깨진 글자
        ocr_text = ("9,564,000 KANOO VEHICLE 4 :\nLEASING B.S.C. JAY 79\nILJINELECTRIC COLTD, 1 cle Lasy 400KV and 220KV Feeder t-ilis 5100/2025/4669 17\n"
                    "34,968,319.628 SOUTH KOREA SIGE 5 Cable Works for\nAwsighl Establishment of New\nSitra 400KV Grid\nSubstations\n"
                    + "\n".join(f"{i},000.000 ALMOAYYED W.L.L. Gleedls lll Procurement {i}" for i in range(40))
                    + "\n120,000.000 KOREA TRADING W.L.L. Supply of uniforms 33/2026 4")
        w.pdf_text = lambda raw: "  "
        w.ocr_pdf = lambda raw: (ocr_text, None)
        get, post, calls = fakes()
        opened = {"id": "bhopen:9001:일진전기", "source": w.BH_OPEN_SOURCE, "published": "2026-10-25", "company": "일진전기", "companies": ["일진전기"],
                  "title": "4669/2025/5100 400kV and 220kV Feeder Cable Works", "bidder": "ILJIN ELECTRIC", "value": 35004118.33, "currency": "BHD",
                  "rank": 1, "priced": 3, "firstSeen": "2026-10-25T17:30:00+09:00", "tier": "A"}
        prev = {"items": [opened], "generatedAt": (NOW - dt.timedelta(days=1)).isoformat(), "pccLastRun": NOW.isoformat(), "bahrainOpenSeen": ["9002", "9003"],
                "bahrainSeen": ["/MediaHandler/GenericHandler/Pdf/Awarded/Awarded Tenders 2026-09.pdf",
                                "/MediaHandler/GenericHandler/Pdf/Awarded/Awarded Tenders 2026-08.pdf"]}
        doc = w.run(now=NOW, previous=prev, get=get, post=post, sleep=lambda s: None)
        # 글자 인식 전에 '스캔 — 미확인'으로 넘긴 최근 두 보고서를 한 번 다시 읽는다
        self.assertEqual(calls["bh_pdf"], 2)
        self.assertEqual(len(doc["bahrainOcr"]), 2)
        bh = [x for x in doc["items"] if x["source"] == "바레인 입찰위원회" and x["id"].startswith("bh:Awarded Tenders 2026-08")]
        iljin = [x for x in bh if x["company"] == "일진전기"]
        self.assertEqual(len(iljin), 1)
        self.assertTrue(iljin[0]["ocr"] and iljin[0]["isNew"])
        self.assertIn("34,968,319.628 SOUTH KOREA", iljin[0]["title"])
        self.assertIn("Sitra 400KV Grid", iljin[0]["title"])
        self.assertEqual(w.tier_of(iljin[0]), "B")
        # 보고서의 거꾸로 적힌 입찰 번호(5100/2025/4669)로 10-25 개찰 기록(4669/2025/5100)과 잇는다
        self.assertEqual(iljin[0]["openedBid"]["id"], "bhopen:9001:일진전기")
        self.assertIn("같은 입찰의 개찰 기록: 2026-10-25 ILJIN ELECTRIC BHD 35,004,118 · 응찰가 1위/3곳 — 월간 낙찰 보고서에 실림", iljin[0]["title"])
        # 이름 줄 옆 국적 칸('SOUTH KOREA')은 따로 잡지 않고, 멀리 떨어진 한국 업체 줄은 C로 남긴다
        others = [x for x in bh if not x["company"]]
        self.assertEqual(len(others), 1)
        self.assertIn("KOREA TRADING", others[0]["title"])
        chk = [c for c in doc["checks"] if c["source"] == "바레인 입찰위원회"]
        self.assertTrue(all("글자 인식(OCR)으로 읽음" in c["note"] for c in chk))
        # 다음 실행은 다시 받지 않는다
        get2, post2, calls2 = fakes()
        w.run(now=NOW + dt.timedelta(hours=11), previous=doc, get=get2, post=post2, sleep=lambda s: None)
        self.assertEqual(calls2["bh_pdf"], 0)

    def test_stored_first_ocr_line_is_tidied(self):
        # 11-02 운영 첫 OCR 저장본 그대로: 앞 낙찰(KANOO)의 끝 두 줄이 붙어 레이더 줄에서 핵심(국적·사업명)이 잘렸다
        x = {"id": "bh:Aug 2026 Awarding Report.pdf:0", "source": "바레인 입찰위원회", "company": "일진전기", "ocr": True,
             "buyer": "바레인 정부 발주처(보고서 줄 참조)", "report": "2 Awarded Tenders Report - August 2026 8.7 MB",
             "title": "9,564,000 KANOO VEHICLE 4 : / LEASING B.S.C. JAY 79 / ILJINELECTRIC COLTD, 1 cle Lasy 400KV and 220KV Feeder t-ilis "
                      "5100/2025/4669 17 / 34,968,319.628 SOUTH KOREA SIGE 5 Cable Works for / Awsighl Establishment of New / Sitra 400KV Grid"}
        w.tidy_ocr_item(x)
        self.assertTrue(x["title"].startswith("ILJINELECTRIC COLTD"))
        self.assertEqual((x["buyer"], x["reportMonth"]), ("정부 발주처(보고서 줄 참조)", "2026-08"))
        w.tidy_ocr_item(x)
        self.assertTrue(x["title"].startswith("ILJINELECTRIC COLTD"))   # 두 번 해도 같음
        self.assertEqual(w.report_month("1 Awarded Tenders Report - September 2026 15.8 MB"), "2026-09")
        self.assertIsNone(w.report_month("Awarded Tenders 2026-09.pdf"))

    def test_ocr_name_rules_and_tools(self):
        self.assertEqual(w.beat_of_ocr("HYOSUNGHEAVY INDUSTRIES"), "효성중공업")
        self.assertEqual(w.beat_of_ocr("LSCABLE & SYSTEM LTD"), "LS전선")
        self.assertIsNone(w.beat_of_ocr("PURPOSCO NTRACT"))        # 붙여 쓴 글자 속 짧은 약어(POSCO)는 안 맞춤
        self.assertIsNone(w.beat_of_ocr("ELECTRICAL CABLE WORKS"))
        self.assertEqual(self._ocr(b"%PDF", which=lambda name: None), (None, "글자 인식 도구 없음"))
        ran = []

        class R:
            def __init__(self, out=""):
                self.returncode, self.stdout = 0, out

        def run(cmd, **kw):
            ran.append(cmd[0])
            if cmd[0] == "pdftoppm":
                for n in (1, 2, 3):
                    open(cmd[-1] + f"-{n}.png", "wb").close()
                return R()
            return R("ILJINELECTRIC COLTD")
        ticks = iter([0, 1, 2, 400, 401])
        text, err = self._ocr(b"%PDF", run=run, which=lambda name: "/usr/bin/" + name, budget=300, clock=lambda: next(ticks))
        self.assertEqual(ran, ["pdftoppm", "tesseract", "tesseract"])
        self.assertIn("ILJINELECTRIC", text)
        self.assertEqual(err, "글자 인식 시간 상한(2/3쪽)")

    def test_world_bank_older_layout_without_vendor_number(self):
        old = dict(WB_AWARD, id="OP00999", notice_text="Awarded Bidder(s): LS CABLE & SYSTEM LTD Country: Korea, Republic of Signed Contract Price USD 12,000,000.00")
        x = w.wb_items([old], "2026-07-01")[0]
        self.assertEqual((x["company"], x["winners"], x["value"]), ("LS전선", ["LS CABLE & SYSTEM LTD"], 12000000.0))

    def test_winners_in_every_language_and_restored_rules(self):
        multi = dict(TED_HYOSUNG, **{"publication-number": "558048-2026", "winner-name": {"swe": ["Koncar D&ST", "Hyosung Heavy Industries Corporation"],
                                                                                         "eng": ["Hyosung Heavy Industries Corporation"]},
                                     "winner-country": ["HRV", "KOR"], "winner-identifier": ["080100322", "578-87-00896"]})
        x = w.ted_items([multi])[0]
        self.assertEqual((x["winners"], x["winnerCount"], x["winnerIds"]), (["Hyosung Heavy Industries Corporation", "Koncar D&ST"], 2, []))
        coin = dict(TED_OTHER_KR, **{"publication-number": "552963-2026", "winner-name": {"fra": ["FR_POONGSAN CORPORATION"]}})
        self.assertIsNone(w.ted_items([coin])[0]["company"])  # 풍산: 출입처 밖
        big = dict(TED_HYOSUNG, **{"publication-number": "741234-2026", "winner-name": {"ces": ["Hyundai Motor Czech s.r.o."]}, "winner-country": ["CZE"],
                                   "result-value-notice": "400000000", "result-value-cur-notice": "CZK"})
        small = dict(big, **{"publication-number": "741235-2026", "result-value-notice": "4002056"})
        self.assertEqual({i["id"]: w.tier_of(i) for i in w.ted_items([big, small])}, {"ted:741234-2026": "B", "ted:741235-2026": "C"})
        # a stored item from an older rule set is re-derived even when not found again
        get, post, _ = fakes(ted_rows=())
        prev = {"items": [dict(w.ted_items([coin])[0], company="풍산", companies=["풍산"], tier="A", firstSeen="2026-10-01T00:00:00+09:00")],
                "generatedAt": "2026-10-28T17:30:00+09:00", "bahrainSeen": ["x"]}
        doc = w.run(now=NOW, previous=prev, get=get, post=post, sleep=lambda s: None)
        stored = next(i for i in doc["items"] if i["id"] == "ted:552963-2026")
        self.assertEqual((stored["company"], stored["tier"]), (None, "C"))

    def test_world_bank_awarded_block_only(self):
        got = {x["id"]: x for x in w.wb_items([WB_AWARD, WB_REJECTED, WB_OLD], "2026-07-01")}
        self.assertEqual(set(got), {"wb:OP00477000"})  # rejected Hyosung and the 2022 notice are dropped
        x = got["wb:OP00477000"]
        self.assertEqual((x["company"], x["buyerCountry"], x["currency"], x["value"]), ("효성중공업", "Iraq", "USD", 38410000.0))
        self.assertEqual(x["winners"], ["HYOSUNG HEAVY INDUSTRIES CORPORATION"])

    def test_fts_supplier_names_and_korean_address(self):
        got = w.fts_items([FTS_REL, FTS_UK_ONLY])
        self.assertEqual(len(got), 1)
        x = got[0]
        self.assertEqual(x["company"], "LS전선")
        self.assertIn("Some Korean Engineering Co", x["winners"])
        self.assertEqual((x["value"], x["currency"], x["url"]), (250000000.0, "GBP", "https://www.find-tender.service.gov.uk/Notice/102400-2026"))

    def test_taiwan_pcc_winners_only_and_detail_once(self):
        got = {x["id"]: x for x in w.pcc_items([PCC_LS, PCC_LOSER, PCC_LSE, PCC_FIBER, PCC_OLD], "2026-07-01")}
        # 탈락(未得標廠商)만인 공고·대한광통신(TAIHAN FIBEROPTICS, 출입처 아님)·창 밖 공고는 버린다
        self.assertEqual(set(got), {"pcc:3.13.31:0081520071:BDM-1-71300001", "pcc:A.15.5.1:SJ01-CCO-02:BDM-2-71290000"})
        ls = got["pcc:3.13.31:0081520071:BDM-1-71300001"]
        self.assertEqual((ls["company"], ls["winners"], ls["winnerCount"], ls["kind"], ls["currency"]), ("LS전선", ["LS Cable & System Ltd."], 2, "낙찰", "TWD"))
        self.assertEqual(ls["url"], "https://openfunltd.github.io/pcc-viewer/tender.html?unit_id=3.13.31&job_number=0081520071")
        self.assertEqual(ls["official"], "https://web.pcc.gov.tw/prkms/tender/common/noticeDate/redirectPublic?ds=20261028&fn=BDM-1-71300001.xml")
        lse = got["pcc:A.15.5.1:SJ01-CCO-02:BDM-2-71290000"]
        self.assertEqual((lse["company"], lse["kind"], w.tier_of(lse)), ("LS일렉트릭", "계약 변경", "B"))  # 중문 대만 지사 이름, 更正決標公告는 B
        self.assertEqual(w.tier_of(ls), "A")
        get, post, calls = fakes()
        first = w.run(now=NOW, previous={"items": [], "generatedAt": (NOW - dt.timedelta(days=10)).isoformat()}, get=get, post=post, sleep=lambda s: None)
        x = next(i for i in first["items"] if i["id"] == ls["id"])
        self.assertTrue(x["isNew"])
        self.assertEqual((x["value"], x["priceKind"], x["concluded"]), (276084986, "출입처 낙찰 품목 결정 금액 합", "2026-10-24"))
        self.assertIn("2번 품목 超耐熱鋼心鋁線ZTACIR 260mm2 LS Cable & System Ltd. NT$276,084,986(원산지 南韓(Republic of Korea))", x["title"])
        self.assertNotIn("582,764,700", x["title"])  # 다른 낙찰자(중화전선) 품목 금액은 넣지 않는다
        self.assertEqual(calls["pcc_detail"], 2)  # 새 공고 두 건만(LS일렉트릭 공고는 상세 없음 → 목록 값 유지)
        lse2 = next(i for i in first["items"] if i["id"] == lse["id"])
        self.assertEqual((lse2["value"], lse2.get("detailError")), (38204450, "상세 없음"))
        self.assertEqual(sum(1 for c in first["checks"] if c["source"] == w.PCC_SOURCE and c["status"] == "ok"), len(w.PCC_TERMS))
        get2, post2, calls2 = fakes()
        second = w.run(now=NOW + dt.timedelta(hours=10), previous=first, get=get2, post=post2, sleep=lambda s: None)
        self.assertEqual((calls2["pcc"], calls2["pcc_detail"]), (0, 0))  # 하루 한 번: 오후 실행은 건너뜀(저장된 공고는 그대로)
        self.assertIn("이번 실행은 건너뜀", next(c for c in second["checks"] if c["source"] == w.PCC_SOURCE)["note"])
        get3, post3, calls3 = fakes()
        third = w.run(now=NOW + dt.timedelta(hours=21), previous=second, get=get3, post=post3, sleep=lambda s: None)
        self.assertEqual((calls3["pcc"], calls3["pcc_detail"]), (len(w.PCC_TERMS), 0))  # 이미 본 공고는 상세를 다시 읽지 않고 저장된 금액을 쓴다
        y = next(i for i in third["items"] if i["id"] == ls["id"])
        self.assertEqual((y["value"], y["isNew"], y["concluded"]), (276084986, False, "2026-10-24"))

    def test_taiwan_pcc_rate_limit_stops_the_run_and_contract_change_title(self):
        calls, waits = [], []

        def get(url, params=None, headers=None, timeout=None):
            calls.append(params.get("query"))
            if len(calls) == 3:
                return Resp({}, status=429)
            return Resp({"records": [PCC_LS]})
        items, checks = w.pcc(NOW - dt.timedelta(days=30), set(), get=get, sleep=waits.append)
        self.assertEqual(len(calls), 3)  # 429 뒤로는 부르지 않는다(상세도)
        st = [c["status"] for c in checks]
        self.assertEqual((st[:2], st[2], set(st[3:])), (["ok", "ok"], "failed", {"failed"}))
        self.assertEqual(checks[3]["error"], "HTTP 429 뒤 이번 실행 중단")
        self.assertEqual(waits[:2], [w.PCC_GAP, w.PCC_GAP])
        self.assertEqual(items[0].get("detailError"), "HTTP 429(상세 다음에)")  # 상세는 시도하지 않고 다음 실행에 다시
        # 다음 실행: 못 읽은 상세를 이번엔 읽고, 저장된 옛 값으로 덮어쓰지 않는다
        prev = {"items": [dict(items[0], firstSeen="2026-10-28T06:50:00+09:00", tier="A")], "generatedAt": (NOW - dt.timedelta(days=1)).isoformat(),
                "pccLastRun": (NOW - dt.timedelta(days=1)).isoformat(), "bahrainSeen": ["x"]}
        g, p, c = fakes(pcc_rows=(PCC_LS,))
        doc = w.run(now=NOW, previous=prev, get=g, post=p, sleep=lambda s: None)
        z = next(i for i in doc["items"] if i["id"] == items[0]["id"])
        self.assertEqual((c["pcc_detail"], z["value"], z.get("detailError")), (1, 276084986, None))
        cco = w.pcc_items([dict(PCC_LS, brief=dict(PCC_LS["brief"], title="臺鐵SJ01標號誌電子聯鎖系統工程第1次契約變更"))], "2026-07-01")[0]
        self.assertEqual((cco["kind"], w.tier_of(cco)), ("계약 변경", "B"))

    def test_baseline_then_new(self):
        get, post, calls = fakes()
        first = w.run(now=NOW, previous=None, get=get, post=post, sleep=lambda s: None)
        self.assertEqual(first["status"], "complete")
        self.assertTrue(all(x["baseline"] and not x["isNew"] for x in first["items"]))
        self.assertEqual(first["windowStart"], (NOW - dt.timedelta(days=w.BASELINE_DAYS)).date().isoformat())
        self.assertEqual(calls["bh_pdf"], 1)  # first run reads only the newest monthly report
        bh = [x for x in first["items"] if x["source"] == "바레인 입찰위원회"]
        self.assertEqual((len(bh), bh[0]["company"], bh[0]["tier"]), (1, "효성중공업", "B"))
        tiers = {x["id"]: x["tier"] for x in first["items"]}
        self.assertEqual((tiers["ted:545946-2026"], tiers["ted:546637-2026"], tiers["ted:721359-2026"]), ("A", "B", "C"))

        new_ted = dict(TED_HYOSUNG, **{"publication-number": "800001-2026", "publication-date": "2026-10-29+01:00"})
        get2, post2, calls2 = fakes(ted_rows=(TED_HYOSUNG, new_ted))
        second = w.run(now=NOW + dt.timedelta(days=1), previous=first, get=get2, post=post2, sleep=lambda s: None)
        new = [x for x in second["items"] if x["isNew"]]
        self.assertEqual([x["id"] for x in new], ["ted:800001-2026"])
        self.assertEqual(second["windowStart"], (NOW - dt.timedelta(days=w.OVERLAP_DAYS)).date().isoformat())
        self.assertEqual(calls2["bh_pdf"], 0)  # both monthly reports already read or remembered
        old = next(x for x in second["items"] if x["id"] == "ted:545946-2026")
        self.assertEqual(old["firstSeen"], NOW.isoformat(timespec="seconds"))

    def test_failures_are_not_zero_and_keep_items(self):
        get, post, _ = fakes()
        first = w.run(now=NOW, previous=None, get=get, post=post, sleep=lambda s: None)

        def bad(*a, **kw):
            return Resp({}, status=503)
        doc = w.run(now=NOW + dt.timedelta(days=1), previous=first, get=bad, post=bad, sleep=lambda s: None)
        self.assertEqual(doc["status"], "failed")
        self.assertEqual(len(doc["items"]), len(first["items"]))
        self.assertTrue(all(c["status"] == "failed" for c in doc["checks"]))
        self.assertEqual(doc["lastSuccess"], first["lastSuccess"])

    def test_bahrain_opened_bids_rank_and_tiers(self):
        rows = w.bh_open_rows(bh_open_page(BH_OPEN_ROWS)["d"])
        self.assertEqual(len(rows), 3)
        r = rows[0]
        self.assertEqual((r["ref"], r["tenderNo"], r["opened"], r["authority"], r["bids"]),
                         ("9001", "4669/2025/5100", "2026-04-13", "Electricity and Water Authority (Planning)", 3))
        self.assertTrue(r["subject"].startswith("400kV and 220kV Feeder Cable Works"))
        self.assertEqual(r["href"], "/OpenedTenderDetails/?id=4669%2f2025%2f5100&source=New&envelope=PB&type=1")
        bids = w.bh_bidders(BH_DETAILS["9001"])
        self.assertEqual([(b["name"], b["value"], b["options"]) for b in bids],
                         [("TAIHAN ELECTRIC WIRE CO LTD", 45648300.0, 2), ("LS CABLE AND SYSTEM LTD", 46659985.55, 1), ("ILJIN ELECTRIC", 35004118.33, 1)])
        got = {x["company"]: x for x in w.bh_open_items(r, bids)}
        self.assertEqual(set(got), {"일진전기", "LS전선", "대한전선"})
        il, ls, th = got["일진전기"], got["LS전선"], got["대한전선"]
        self.assertEqual((il["rank"], il["priced"], il["lowest"], il["lowestBid"], w.tier_of(il)), (1, 3, True, None, "A"))
        self.assertEqual([o["name"] for o in il["others"]], ["TAIHAN ELECTRIC WIRE CO LTD", "LS CABLE AND SYSTEM LTD"])
        self.assertEqual((ls["rank"], ls["lowestBid"], w.tier_of(ls)), (3, {"name": "ILJIN ELECTRIC", "value": 35004118.33}, "B"))
        self.assertEqual((th["rank"], th["options"], th["value"]), (2, 2, 45648300.0))  # 옵션 응찰은 낮은 옵션 값
        self.assertEqual((il["kind"], il["winners"], il["envelope"], il["currency"]), ("개찰(응찰)", [], "PB", "BHD"))
        self.assertEqual(il["url"], "https://www.tenderboard.gov.bh/OpenedTenderDetails/?id=4669%2f2025%2f5100&source=New&envelope=PB&type=1")
        # 응찰가 없는 단계(기술·자격)와 탈락 응찰: 순위 없음, 출입처라도 B
        tq = {x["company"]: x for x in w.bh_open_items(rows[2], w.bh_bidders(BH_DETAILS["9003"]))}
        self.assertEqual((tq["LS일렉트릭"]["rank"], tq["LS일렉트릭"]["lowest"], w.tier_of(tq["LS일렉트릭"])), (None, False, "B"))
        self.assertEqual((tq["효성중공업"]["bidStatus"], tq["효성중공업"]["rank"]), ("Rejected", None))
        self.assertEqual(w.bh_open_items(rows[1], w.bh_bidders(BH_DETAILS["9002"])), [])  # 한국 응찰 없음
        small = dict(il, value=80000.0)
        self.assertEqual(w.tier_of(small), "B")  # 최저가라도 작은 입찰은 B

    def test_bahrain_opened_first_run_is_baseline_then_new(self):
        prev = {"items": [], "generatedAt": (NOW - dt.timedelta(days=1)).isoformat(), "bahrainSeen": ["x"], "pccLastRun": NOW.isoformat()}
        get, post, calls = fakes(bh_open=BH_OPEN_ROWS[1:])
        first = w.run(now=NOW, previous=prev, get=get, post=post, sleep=lambda s: None)
        self.assertEqual((calls["bh_open"], calls["bh_open_detail"]), (2, 2))  # 2쪽은 비어 목록 끝
        ls = next(x for x in first["items"] if x["source"] == w.BH_OPEN_SOURCE and x["company"] == "LS일렉트릭")
        self.assertEqual((ls["baseline"], ls["isNew"]), (True, False))  # 이 원천의 첫 실행은 기준선
        self.assertEqual(sorted(first["bahrainOpenSeen"]), ["9002", "9003"])
        chk = next(c for c in first["checks"] if c["source"] == w.BH_OPEN_SOURCE)
        self.assertEqual((chk["status"], chk["returned"], chk["matched"]), ("ok", 2, 2))
        self.assertIn("바레인 입찰위원회 월간 낙찰 보고서·개찰 결과", first["coverage"])
        get2, post2, calls2 = fakes()
        second = w.run(now=NOW + dt.timedelta(hours=10), previous=first, get=get2, post=post2, sleep=lambda s: None)
        self.assertEqual(calls2["bh_open"], 2)  # 2쪽에서 목록 끝
        self.assertEqual(calls2["bh_open_detail"], 1)  # 새 개찰(9001)만 상세를 읽는다
        new = [x for x in second["items"] if x["isNew"]]
        self.assertEqual(sorted(x["company"] for x in new), ["LS전선", "대한전선", "일진전기"])
        il = next(x for x in new if x["company"] == "일진전기")
        self.assertEqual((il["tier"], il["published"]), ("A", "2026-04-13"))
        # 다시 봐도 상세를 다시 읽지 않고, 저장된 응찰 항목은 응찰자 이름으로 출입처를 유지한다(낙찰자 칸이 비어 있어도)
        get3, post3, calls3 = fakes()
        third = w.run(now=NOW + dt.timedelta(hours=21), previous=second, get=get3, post=post3, sleep=lambda s: None)
        self.assertEqual(calls3["bh_open_detail"], 0)
        il3 = next(x for x in third["items"] if x["id"] == il["id"])
        self.assertEqual((il3["company"], il3["tier"], il3["isNew"]), ("일진전기", "A", False))

    def test_bahrain_opened_first_run_cap_remembers_the_rest(self):
        cap = w.BH_OPEN_DETAIL_MAX
        w.BH_OPEN_DETAIL_MAX = 1
        try:
            get, post, calls = fakes()
            _, checks, seen = w.bahrain_opened(None, get=get, post=post, sleep=lambda s: None)
            self.assertEqual((calls["bh_open_detail"], sorted(seen)), (1, ["9001", "9002", "9003"]))
            self.assertIn("첫 실행 기준선 — 예전 개찰 2건은 읽지 않음", checks[0]["note"])
            _, checks2, seen2 = w.bahrain_opened(["9001"], get=get, post=post, sleep=lambda s: None)
            self.assertEqual((sorted(seen2), checks2[0]["note"].split(" · ")[-1]), (["9001", "9002"], "남은 1건은 다음 실행에"))
        finally:
            w.BH_OPEN_DETAIL_MAX = cap

    def test_bahrain_opened_list_failure_is_not_zero(self):
        prev = {"items": [], "generatedAt": (NOW - dt.timedelta(days=1)).isoformat(), "bahrainSeen": ["x"], "bahrainOpenSeen": ["9002"],
                "pccLastRun": NOW.isoformat()}
        get, post, _ = fakes(bh_open=())
        doc = w.run(now=NOW, previous=prev, get=get, post=post, sleep=lambda s: None)
        chk = [c for c in doc["checks"] if c["source"] == w.BH_OPEN_SOURCE]
        self.assertEqual((chk[0]["status"], chk[0]["error"]), ("failed", "목록 형식 미상(0줄)"))
        self.assertEqual(doc["bahrainOpenSeen"], ["9002"])  # 기억은 그대로
        self.assertEqual(doc["status"], "partial")

    def test_ted_429_waits_once(self):
        state = {"n": 0}
        waits = []

        def post(url, json=None, headers=None, timeout=None):
            state["n"] += 1
            return Resp({}, status=429) if state["n"] == 1 else Resp({"notices": [TED_HYOSUNG], "totalNoticeCount": 1})
        rows, total = w.ted_search("q", post=post, sleep=waits.append)
        self.assertEqual((len(rows), total, waits), (1, 1, [15]))


if __name__ == "__main__":
    unittest.main()
