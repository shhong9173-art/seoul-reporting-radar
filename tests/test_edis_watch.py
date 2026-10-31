"""USITC EDIS 감시: 10-31 탐침의 실제 XML 모양(results/documents/document, 값 이중 이스케이프)·문서 종류 이름 그대로의 가짜 응답으로
분류(한국산 청원 A, 출입처 서면 B, 지켜보는 337 결정 B, 질문서·출석 통지·상대방 서면·OUII 서면 C, 네덜란드 OCI 아님),
첫 실행 기준선, 다음 실행의 새 문서만 이벤트, 337 제소장 표지의 출입처 이름(A)·지켜보기 추가, 본문 발췌(요청 문장 먼저, 목차 건너뜀),
토큰 미설정·만료·거부·3일 안 만료, 목록 실패는 미확인, 쪽 상한 공백 표시."""
import base64
import datetime as dt
import json
import sys
import unittest
from pathlib import Path
from unittest import mock
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import edis_watch as w  # noqa: E402
import trade_remedy_watch as trw  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 2, 7, 40, tzinfo=KST)
NOSLEEP = lambda s: None  # noqa: E731
INV337 = "Certain TOPCon Solar Cells, Modules, Panels, Components Thereof, and Products Containing Same"


def jwt(exp):
    part = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")  # noqa: E731
    return f"{part({'alg': 'HS256'})}.{part({'sub': 'x', 'exp': int(exp.timestamp())})}.sig"


TOKEN = jwt(NOW + dt.timedelta(days=12))


def doc(i, dtype, received, *, title="", inv="337-1494", itype="Sec 337", ititle=INV337, phase="Violation", status="Active",
        firm="Sidley Austin LLP", by="", sec="Public"):
    vals = {"id": str(i), "documentType": dtype, "documentTitle": title or dtype, "securityLevel": sec, "investigationNumber": inv,
            "investigationPhase": phase, "investigationStatus": status, "investigationTitle": ititle, "investigationType": itype,
            "firmOrganization": firm, "filedBy": "A. Lawyer", "onBehalfOf": by, "documentDate": received[:10] + " 00:00:00",
            "officialReceivedDate": received, "actionJacketControlNumber": "", "memorandumControlNumber": "",
            "attachmentListUri": f"https://edis.usitc.gov/data/attachment/{i}", "modifiedDate": received}
    # EDIS는 값을 두 번 이스케이프해 보낸다(탐침: XML 해석 뒤에도 &amp;)
    return "<document>" + "".join(f"<{k}>{escape(escape(v))}</{k}>" for k, v in vals.items()) + "</document>"


def listing(docs):
    return "<results><documents>" + "".join(docs) + "</documents></results>"


HANWHA = "Hanwha Solutions Corporation; Hanwha Q CELLS USA, Inc.; Hanwha Q CELLS America Inc. & others"


def pdf(lines_per_page):
    """pypdf가 읽을 수 있는 최소 PDF(쪽마다 글줄)."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for lines in lines_per_page:
        stream = "BT /F1 9 Tf 20 760 Td 11 TL " + " ".join(f"({x.replace('(', '').replace(')', '')}) '" for x in lines) + " ET"
        objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {len(objs)} 0 R /Resources << /Font << /F1 3 0 R >> >> >>")
        kids.append(len(objs))
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>"
    body, offs = "%PDF-1.4\n", []
    for n, o in enumerate(objs, 1):
        offs.append(len(body.encode("latin-1")))
        body += f"{n} 0 obj\n{o}\nendobj\n"
    x = len(body.encode("latin-1"))
    body += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n" + "".join(f"{o:010d} 00000 n \n" for o in offs)
    body += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n"
    return body.encode("latin-1")


PETITION_PDF = pdf([
    ["UNITED STATES INTERNATIONAL TRADE COMMISSION", "Washington, D.C.", "TABLE OF CONTENTS ........................ 1"],
    ["Respondents Hanwha Solutions Corporation and Hanwha Q CELLS USA, Inc. join this petition.",
     "Respondents respectfully request that the Commission review the ID and terminate the investigation with prejudice.",
     "The Commission should not permit Complainant to refile the same claims."],
])
COMPLAINT_PDF = pdf([
    ["COMPLAINT UNDER SECTION 337 OF THE TARIFF ACT OF 1930", "Proposed Respondents:", "Hyundai Mobis Co., Ltd., Seoul, Republic of Korea"],
    ["Complainant requests that the Commission issue a limited exclusion order against the Proposed Respondents."],
    ["Background of the technology."], ["Infringement chart."],
])


class R:
    def __init__(self, code=200, text="", content=b""):
        self.status_code, self.text, self.content = code, text, content


def fake(pages, by_inv=None, *, attach=None, files=None, calls=None, list_code=200):
    """pages: [[doc xml...], ...] 전체 목록 쪽. by_inv: 조사번호 → [doc xml]. attach: 문서 id → 첨부 XML. files: 다운로드 URL → (코드, 바이트)."""
    def get(url, params=None, headers=None, timeout=None):
        if calls is not None:
            calls.append((url, dict(params or {}), "Authorization" in (headers or {})))
        if url.endswith("/document") and params and params.get("investigationNumber"):
            return R(text=listing((by_inv or {}).get(params["investigationNumber"], [])))
        if url.endswith("/document"):
            if list_code != 200:
                return R(list_code, "error")
            p = int(params["pageNumber"])
            return R(text=listing(pages[p - 1] if p <= len(pages) else []))
        if "/attachment/" in url:
            i = url.rsplit("/", 1)[1]
            return R(text=(attach or {}).get(i, "<results><attachments></attachments></results>"))
        code, data = (files or {}).get(url, (404, b""))
        if code == 200 and not (headers or {}).get("Authorization"):
            return R(401, "", b"")
        if code == 200 and "xml" in (headers or {}).get("Accept", ""):
            return R(406, "", b"")  # 탐침 29: 다운로드에 Accept: application/xml이면 406
        return R(code, "", data)
    return get


def att(i, size=400000):
    return (f"<results><attachments><attachment><id>9{i}</id><documentId>{i}</documentId><title>x.pdf</title><fileSize>{size}</fileSize>"
            f"<pageCount>2</pageCount><downloadUri>https://edis.usitc.gov/data/download/{i}/9{i}</downloadUri></attachment></attachments></results>")


def dl(i):
    return f"https://edis.usitc.gov/data/download/{i}/9{i}"


class Parse(unittest.TestCase):
    def test_double_escaped_values_and_namespace(self):
        xml = listing([doc(898408, "Petition", "2026/10/21 16:30:00", by=HANWHA)]).replace("<results>", '<results xmlns="urn:x">')
        d = w.parse_docs(xml)[0]
        self.assertEqual(d["onBehalfOf"], HANWHA)
        self.assertEqual(d["officialReceivedDate"], "2026/10/21 16:30:00")

    def test_token_expiry(self):
        self.assertEqual(w.token_expiry(TOKEN), (NOW + dt.timedelta(days=12)).astimezone(dt.timezone.utc))
        self.assertIsNone(w.token_expiry("not-a-jwt"))


class Classify(unittest.TestCase):
    def c(self, x, watched=("337-1494",)):
        return w.classify(w.parse_docs(listing([x]))[0], dict.fromkeys(watched, "seed"))

    def test_korea_petition_is_a(self):
        t, why, _ = self.c(doc(1, "Petition", "2026/10/30 10:00:00", inv="731-TA-1800", itype="Import Injury", phase="Prelim",
                               ititle="Certain Cold-Rolled Steel Flat Products from Korea", firm="Wiley Rein LLP", by="Steel Dynamics"))
        self.assertEqual(t, "A")

    def test_beat_party_petition_is_b(self):
        t, why, who = self.c(doc(898408, "Petition", "2026/10/21 16:30:00", title="Respondents' Petition for Review", by=HANWHA))
        self.assertEqual((t, who), ("B", ["한화솔루션"]))

    def test_commission_notice_in_watched_case_is_b(self):
        t, why, _ = self.c(doc(899140, "Notice", "2026/10/29 09:00:00", firm="USITC", title="Commission Determination to Extend the Due Date for Determining Whether to Review an Initial Determination"))
        self.assertEqual(t, "B")

    def test_routine_and_other_side_are_c(self):
        for x in (doc(2, "Questionnaire - Foreign Producer", "2026/10/30 10:00:00", inv="731-TA-1800", itype="Import Injury",
                      ititle="Certain Cold-Rolled Steel Flat Products from Korea", firm="USITC", by="POSCO", sec="Confidential"),
                  doc(3, "Notice of Appearance", "2026/10/30 10:00:00", by="Hyundai Steel Company"),
                  doc(4, "Motion Response/Reply", "2026/10/30 10:00:00", firm="Alston & Bird", by="First Solar, Inc."),
                  doc(5, "Motion Response/Reply", "2026/10/30 10:00:00", firm="USITC", title="OUII response")):
            self.assertEqual(self.c(x)[0], "C", x)

    def test_procedural_alj_orders_are_c_but_termination_order_and_commission_order_b(self):
        self.assertEqual(self.c(doc(20, "Order", "2026/10/30 10:00:00", firm="USITC", title="Order No. 41: Granting Motion for Leave to File Reply"))[0], "C")
        self.assertEqual(self.c(doc(21, "Order", "2026/10/30 10:00:00", firm="USITC", title="Order No. 42: Initial Determination Terminating Respondent"))[0], "B")
        self.assertEqual(self.c(doc(22, "Order, Commission", "2026/10/30 10:00:00", firm="USITC", title="Commission Order"))[0], "B")
        self.assertEqual(self.c(doc(23, "ID/RD - Other Than Final on Violation", "2026/10/30 10:00:00", firm="USITC"))[0], "B")

    def test_procedural_notice_and_staff_filings_are_c(self):
        # 운영 10-31 첫 실행: 판사 '대리 자문관 교체 안내'·OUII 'Notice of Prior Art'가 B였다
        self.assertEqual(self.c(doc(24, "Notice", "2026/09/11 08:59:00", firm="USITC", title="Notice to the Parties regarding Substitute Attorney Advisor"))[0], "C")
        self.assertEqual(self.c(doc(25, "Notice of Prior Art", "2026/08/07 13:27:00", firm="USITC", title="Commission Investigative Staff's Notice of Prior Art"))[0], "C")
        self.assertEqual(self.c(doc(26, "Notice", "2026/10/29 16:14:00", firm="USITC",
                                    title="Commission Determination to Extend the Due Date for Determining Whether to Review an Initial Determination"))[0], "B")

    def test_party_hits_name_the_beat_entities_in_a_long_joint_list(self):
        ob = ("Canadian Solar Inc., Canadian Solar (USA) Inc., JinkoSolar Holding Co., Ltd., Hanwha Solutions Corporation, "
              "Hanwha Q CELLS USA, Inc., Trina Solar Co., Ltd.")
        self.assertEqual(w.party_hits(ob), ["Hanwha Solutions Corporation", "Hanwha Q CELLS USA, Inc."])

    def test_korea_title_vii_schedule_notice_is_c_but_views_b(self):
        base = dict(inv="731-TA-1800", itype="Import Injury", ititle="Certain Cold-Rolled Steel Flat Products from Korea", firm="USITC")
        self.assertEqual(self.c(doc(6, "Notice", "2026/10/30 10:00:00", **base))[0], "C")
        self.assertEqual(self.c(doc(7, "Opinion, Commission", "2026/10/30 10:00:00", **base))[0], "B")

    def test_dutch_oci_is_not_oci(self):
        x = doc(8, "Brief - Post-Hearing/Conference", "2026/10/30 10:00:00", inv="731-TA-1600", itype="Import Injury", phase="Final",
                ititle="Urea Ammonium Nitrate Solutions from Russia and Trinidad", by="OCI N.V.; OCI Nitrogen B.V.")
        self.assertIsNone(self.c(x)[0])
        self.assertEqual(trw.BEAT_NAMES[[n for n, _ in trw.BEAT_NAMES].index("OCI")][0], "OCI")
        self.assertTrue(w.companies_in("OCI Company Ltd. and OCI Holdings"))


class Snippets(unittest.TestCase):
    def test_all_caps_caption_is_skipped(self):
        text = ("In the Matter of CERTAIN TOPCON SOLAR CELLS, MODULES, PANELS INVESTIGATION NO. 337-TA-1494 RESPONDENTS PETITION TO TERMINATE THE "
                "INVESTIGATION PUBLIC VERSION. Respondents seek review of Order No. 47, which rejected the request to terminate with prejudice.")
        self.assertEqual(w.snippets(text, []), ["Respondents seek review of Order No. 47, which rejected the request to terminate with prejudice."])

    def test_request_sentences_first_and_toc_skipped(self):
        text = ("TABLE OF CONTENTS ........................ 1. Respondents Hanwha Solutions Corporation join this petition in full. "
                "Respondents respectfully request that the Commission review the ID. The ALJ erred in law here and there. "
                "The Commission should not permit Complainant to refile the same claims.")
        s = w.snippets(text, ["한화솔루션"])
        self.assertEqual(len(s), 3)
        self.assertTrue(s[0].startswith("Respondents Hanwha"))
        self.assertFalse(any("....." in x for x in s))


def first_run(**k):
    pages = [[doc(898800, "Response", "2026/10/31 06:00:00", firm="Alston & Bird", by="First Solar, Inc."),
              doc(10, "PO Subscription", "2026/10/30 12:00:00", inv="337-1500", firm="X LLP")],
             [doc(11, "Notice", "2026/10/29 09:00:00", inv="701-TA-700", itype="Import Injury", firm="USITC", ititle="Steel Nails from Vietnam")]]
    by_inv = {"337-1494": [doc(899140, "Notice", "2026/10/29 09:00:00", firm="USITC", title="Commission Determination to Extend the Due Date for Determining Whether to Review an Initial Determination"),
                           doc(898408, "Petition", "2026/10/21 16:30:00", title="Respondents' Petition for Review", by=HANWHA),
                           doc(898800, "Response", "2026/10/31 06:00:00", firm="Alston & Bird", by="First Solar, Inc.")]}
    calls = []
    get = fake(pages, by_inv, attach={"898408": att(898408), "899140": att(899140)},
               files={dl(898408): (200, PETITION_PDF), dl(899140): (200, pdf([["The Commission has determined to extend the date."]]))}, calls=calls)
    return w.collect(None, NOW, get=get, token=k.get("token", TOKEN), sleep=NOSLEEP), calls


class Collect(unittest.TestCase):
    def test_first_run_is_a_baseline_with_bodies_but_no_events(self):
        (ed, events, check), calls = first_run()
        self.assertEqual(events, [])
        self.assertEqual(check["status"], "ok")
        tiers = {x["id"]: x["tier"] for x in ed["docs"]}
        self.assertEqual(tiers, {"899140": "B", "898408": "B", "898800": "C"})
        pet = next(x for x in ed["docs"] if x["id"] == "898408")
        self.assertEqual(pet["pages"], 2)
        self.assertTrue(any("with prejudice" in s for s in pet["snippets"]))
        self.assertTrue(any("refile" in s for s in pet["snippets"]))
        self.assertEqual(ed["lastReceived"], "2026/10/31 06:00:00")
        self.assertIn("337-1494", ed["watched"])
        self.assertEqual(ed["tokenExpires"], "2026-11-13T22:40:00+00:00")
        # 다운로드에만 토큰을 붙인다(목록·첨부 목록은 익명)
        self.assertTrue(all(auth == ("/download/" in url) for url, _, auth in calls))

    def test_next_run_events_only_for_new_docs_and_complaint_cover_names(self):
        (ed, _, _), _ = first_run()
        later = NOW + dt.timedelta(days=1)
        pages = [[doc(900100, "Brief on Review/Remedy", "2026/11/02 15:00:00", title="Respondents' brief", by=HANWHA),
                  doc(900101, "Complaint", "2026/11/02 14:00:00", inv="337-3900", status="Preinstitution", title="Complaint", by="Acme Corp."),
                  doc(900102, "Complaint", "2026/11/02 13:00:00", inv="337-3901", status="Preinstitution", title="Complaint", by="Other Inc."),
                  doc(899140, "Notice", "2026/10/29 09:00:00", firm="USITC", title="Commission Determination to Extend the Due Date for Determining Whether to Review an Initial Determination"),
                  doc(898800, "Response", "2026/10/31 06:00:00", firm="Alston & Bird", by="First Solar, Inc.")]]
        get = fake(pages, attach={"900100": att(900100), "900101": att(900101), "900102": att(900102)},
                   files={dl(900100): (200, PETITION_PDF), dl(900101): (200, COMPLAINT_PDF),
                          dl(900102): (200, pdf([["COMPLAINT", "Proposed Respondents: Foo Ltd."]]))})
        ed2, events, check = w.collect(ed, later, get=get, token=TOKEN, sleep=NOSLEEP)
        self.assertEqual(check["status"], "ok", check)
        by = {e["id"]: e for e in events}
        self.assertEqual(sorted(by), ["edis:900100", "edis:900101"])
        self.assertEqual(by["edis:900101"]["tier"], "A")
        self.assertEqual(by["edis:900101"]["companies"], ["현대모비스"])
        self.assertIn("피제소인 후보", by["edis:900101"]["text"])
        self.assertIn("exclusion order", by["edis:900101"]["text"])
        self.assertEqual(by["edis:900100"]["tier"], "B")
        self.assertIn("337-3900", ed2["watched"])
        self.assertNotIn("337-3901", ed2["watched"])
        self.assertIn("900102", ed2["seen"])  # 이름 없는 제소장은 다시 읽지 않음
        self.assertEqual(ed2["lastReceived"], "2026/11/02 15:00:00")

    def test_old_backfill_docs_of_a_newly_watched_case_are_not_events(self):
        (ed, _, _), _ = first_run()
        pages = [[doc(900200, "Answer to Complaint", "2026/11/02 15:00:00", inv="337-1450", by="Hyundai Mobis Co., Ltd.",
                      title="Response of Hyundai Mobis to the Complaint"),
                  doc(898800, "Response", "2026/10/31 06:00:00", firm="Alston & Bird", by="First Solar, Inc.")]]
        by_inv = {"337-1450": [doc(900200, "Answer to Complaint", "2026/11/02 15:00:00", inv="337-1450", by="Hyundai Mobis Co., Ltd."),
                               doc(880000, "Order", "2026/09/01 09:00:00", inv="337-1450", firm="USITC", title="Order No. 3")]}
        calls = []
        ed2, events, _ = w.collect(ed, NOW + dt.timedelta(days=1), get=fake(pages, by_inv, calls=calls), token="", sleep=NOSLEEP)
        self.assertEqual([e["id"] for e in events], ["edis:900200"])
        self.assertIn("337-1450", ed2["watched"])
        self.assertTrue(any(x["id"] == "880000" and not x["isNew"] for x in ed2["docs"]))
        self.assertEqual([p.get("investigationNumber") for _, p, _ in calls if p.get("investigationNumber")], ["337-1450"])

    def test_no_token_expired_and_rejected(self):
        (ed, _, check), calls = first_run(token="")
        self.assertEqual(check["status"], "partial")
        self.assertIn("EDIS_API_TOKEN 미설정", check["error"])
        self.assertFalse(any("/download/" in u for u, _, _ in calls))
        (ed, _, check), calls = first_run(token=jwt(NOW - dt.timedelta(hours=1)))
        self.assertIn("토큰 만료", check["error"])
        self.assertFalse(any("/download/" in u for u, _, _ in calls))
        get = fake([[doc(898408, "Petition", "2026/10/31 16:30:00", by=HANWHA)]], attach={"898408": att(898408)},
                   files={dl(898408): (401, b"")})
        ed, _, check = w.collect(None, NOW, get=get, token=TOKEN, sleep=NOSLEEP)
        self.assertEqual(check["status"], "partial")
        self.assertIn("토큰 거부", ed["tokenNote"])

    def test_expiry_within_three_days_warns_but_still_reads(self):
        (ed, _, check), calls = first_run(token=jwt(NOW + dt.timedelta(days=2)))
        self.assertEqual(check["status"], "ok")
        self.assertIn("만료 예정", ed["tokenNote"])
        self.assertTrue(any("/download/" in u for u, _, _ in calls))

    def test_stored_procedural_b_docs_are_retiered_c_and_get_party_hits(self):
        (ed, _, _), _ = first_run()
        stored = dict(next(x for x in ed["docs"] if x["id"] == "899140"), id="894502", tier="B",
                      documentTitle="Notice to the Parties regarding Substitute Attorney Advisor")
        stored.pop("partyHits", None)
        ed["docs"].append(stored)
        pages = [[doc(898800, "Response", "2026/10/31 06:00:00", firm="Alston & Bird", by="First Solar, Inc.")]]
        ed2, events, _ = w.collect(ed, NOW + dt.timedelta(days=1), get=fake(pages), token="", sleep=NOSLEEP)
        x = next(x for x in ed2["docs"] if x["id"] == "894502")
        self.assertEqual((x["tier"], x["retiered"], x["partyHits"]), ("C", "B", []))
        self.assertEqual(next(x for x in ed2["docs"] if x["id"] == "899140")["tier"], "B")
        self.assertEqual(next(x for x in ed2["docs"] if x["id"] == "898408")["partyHits"], ["Hanwha Solutions Corporation", "Hanwha Q CELLS USA, Inc.",
                                                                                           "Hanwha Q CELLS America Inc."])

    def test_list_failure_is_unconfirmed_and_run_keeps_previous_state(self):
        (ed, _, _), _ = first_run()
        _, events, check = w.collect(ed, NOW + dt.timedelta(days=1), get=fake([], list_code=503), token=TOKEN, sleep=NOSLEEP)
        self.assertEqual((check["status"], events), ("failed", []))
        cfg = {"taricSeeds": [], "pages": []}
        get = fake([], list_code=503)

        def any_get(url, params=None, headers=None, timeout=None):
            if "edis.usitc.gov" in url:
                return get(url, params=params, headers=headers, timeout=timeout)
            return R(503, "down")
        doc_ = trw.run(cfg, now=NOW + dt.timedelta(days=1), previous={"edis": ed, "generatedAt": NOW.isoformat()}, get=any_get,
                       sleep=NOSLEEP, edis_get=get, edis_token=TOKEN)
        self.assertTrue(doc_["edis"]["stale"])
        self.assertEqual(doc_["edis"]["lastReceived"], ed["lastReceived"])
        self.assertIn("USITC EDIS 문서", [c["source"] for c in doc_["checks"]])

    def test_page_cap_without_reaching_last_run_is_partial(self):
        (ed, _, _), _ = first_run()
        pages = [[doc(950000 + p * 10 + i, "PO Subscription", f"2026/11/0{5 - p} 1{i}:00:00", inv="337-1500", firm="X LLP") for i in range(3)]
                 for p in range(w.MAX_PAGES)]
        with mock.patch.object(w, "MAX_PAGES", 3):
            _, _, check = w.collect(ed, NOW + dt.timedelta(days=4), get=fake(pages), token=TOKEN, sleep=NOSLEEP)
        self.assertEqual(check["status"], "partial")
        self.assertIn("일부 미확인", check["error"])

    def test_second_petition_of_the_same_new_korea_case_is_c(self):
        base = dict(inv="731-TA-1800", itype="Import Injury", phase="Prelim", ititle="Certain Cold-Rolled Steel Flat Products from Korea",
                    firm="Wiley Rein LLP", by="Steel Dynamics")
        (ed, _, _), _ = first_run()
        pages = [[doc(960001, "Petition", "2026/11/02 10:00:00", title="Petition Volume I", **base),
                  doc(960002, "Petition", "2026/11/02 10:05:00", title="Petition Volume II", **base),
                  doc(898800, "Response", "2026/10/31 06:00:00", firm="Alston & Bird", by="First Solar, Inc.")]]
        _, events, _ = w.collect(ed, NOW + dt.timedelta(days=1), get=fake(pages), token="", sleep=NOSLEEP)
        self.assertEqual([(e["id"], e["tier"]) for e in events], [("edis:960001", "A")])


if __name__ == "__main__":
    unittest.main()
