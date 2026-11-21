"""태국 무역구제 공고 감시 — 탐침 23(11-19)의 실제 목록·사건 쪽 글(태국어) 모양으로."""
import datetime as dt
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import th_trade_remedy_watch as w  # noqa: E402

KST = w.KST
NOW = dt.datetime(2026, 11, 19, 12, 10, tzinfo=KST)
KR = "สาธารณรัฐเกาหลี"
TIN = "เหล็กแผ่นชุบหรือเคลือบด้วยดีบุกทั้งชนิดเป็นม้วนและไม่เป็นม้วน"
CHROME = "สินค้าเหล็กแผ่นชุบหรือเคลือบด้วยโครเมียมทั้งชนิดเป็นม้วนและไม่เป็นม้วน"
BOND = ("ประกาศคณะกรรมการพิจารณาการทุ่มตลาดและการอุดหนุน เรื่อง ให้เรียกหลักประกันการชำระอากรตอบโต้การทุ่มตลาดในระหว่างการพิจารณาทบทวนการเรียกเก็บอากร"
        "ตอบโต้การทุ่มตลาดต่อไปตามมาตรา ๕๗ กรณีสินค้า" + TIN + " ที่มีแหล่งกำเนิดจากสาธารณรัฐประชาชนจีน สาธารณรัฐเกาหลี ไต้หวัน และสหภาพยุโรป พ.ศ. ๒๕๖๙")
REVIEW = ("ประกาศคณะกรรมการพิจารณาการทุ่มตลาดและการอุดหนุน เรื่อง การเปิดการไต่สวนทบทวนความจำเป็นในการใช้มาตรการตอบโต้การทุ่มตลาดต่อไป กรณีสินค้า"
          + TIN + " ที่มีแหล่งกำเนิดจากสาธารณรัฐประชาชนจีน สาธารณรัฐเกาหลี ไต้หวัน และสหภาพยุโรป")
INIT = "ประกาศกรมการค้าต่างประเทศ เรื่อง การเปิดการไต่สวนการทุ่มตลาดสินค้าเหล็กแผ่นรีดร้อน ที่มีแหล่งกำเนิดจากสาธารณรัฐเกาหลี"


def block(code, product, countries, status, typ, applies, date, origin="ที่มีแหล่งกำเนิดจาก"):
    return (f'<div class="card"><a href="https://thaitr.dft.go.th/th/search/{code}">รายละเอียด</a><p>{code} {product}</p>'
            f'<p>{origin} : {countries}</p><small style="float: right">ดูเพิ่มเติม</small><p>สถานะ : {status}</p>'
            f'<span>{typ}</span> | <span>{applies}</span> <span>วันที่ : {date}</span></div>')


def listing(*blocks):
    return "<html><body>" + "".join(blocks) + "</body></html>"


B1044 = block("AD1044", CHROME, f"สาธารณรัฐประชาชนจีน, {KR}, และ สหภาพยุโรป", "ใช้มาตรการและอยู่ระหว่างการทบทวน", "AD", "ไทยใช้มาตรการ", "11 พ.ย. 2569")
B1212 = block("AD1212", TIN, f"สาธารณรัฐประชาชนจีน, ไต้หวัน, สหภาพยุโรป, และ {KR}", "ใช้มาตรการและอยู่ระหว่างการทบทวน", "AD", "ไทยใช้มาตรการ", "11 พ.ย. 2569")
B2322 = block("AD2322", "Aluminium Extrusion Profiles, Structures and Articles thereof", "สาธารณรัฐอินเดีย", "อยู่ระหว่างการไต่สวน", "AD", "ไทยถูกใช้มาตรการ",
              "09 พ.ย. 2569", origin="ประเทศผู้ใช้มาตรการ")
B1058 = block("AD1058", "ฟีโนลิกเรซิน", "สาธารณรัฐประชาชนจีน, สาธารณรัฐอินโดนีเซีย, และ ไต้หวัน", "อยู่ระหว่างการไต่สวน", "AD", "ไทยใช้มาตรการ", "06 พ.ย. 2569")


STEP_REVIEW = ("<tr><td>2.1 ประกาศกรมการค้าต่างประเทศ เรื่อง เปิดการทบทวนการเรียกเก็บอากรตอบโต้การทุ่มตลาดต่อไป</td><td>11 พ.ย. 2569</td>"
               "<td><a href='/storage/steps/R21.pdf'>pdf</a></td></tr>")


def case_page(anns, rate="0 - 22.67", extra=""):
    links = "".join(f'<a href="https://thaitr.dft.go.th/storage/announcements/{k}.pdf" target="_blank" title="{t}">{t[:20]}</a>' for k, t in anns)
    return ("<html><table><tr><td>สถานะ</td><td>ใช้มาตรการและอยู่ระหว่างการทบทวน</td></tr>"
            f"<tr><td>ประกาศที่เกี่ยวข้อง</td><td>{links}</td></tr>"
            "<tr><td>อากรที่เรียกเก็บ (กรุณาศึกษาข้อมูลโดยละเอียดในประกาศ)</td><td>สาธารณรัฐประชาชนจีน ร้อยละ 0 - 17.46 ของราคา ซี ไอ เอฟ "
            f"{KR} ร้อยละ {rate} ของราคา ซี ไอ เอฟ ไต้หวัน ร้อยละ 4.28 - 20.45 ของราคา ซี ไอ เอฟ รายละเอียดตามประกาศคณะกรรมการ</td></tr>"
            "<tr><td>วันที่เริ่มต้นเรียกเก็บอากร 13 พ.ย. 2569</td></tr><tr><td>วันที่เริ่มต้นเรียกเก็บอากร 11 พ.ย. 2569</td></tr>"
            "<tr><td>วันที่สิ้นสุดเรียกเก็บอากร 12 พ.ย. 2570</td></tr>"
            "<tr><td>ขั้นตอนการไต่สวน</td><td>เริ่มต้น</td><td>สิ้นสุด</td></tr><tr><td>1 กระบวนการไต่สวน</td></tr>"
            "<tr><td>1.1 เปิดไต่สวน</td><td>07 เม.ย. 2563</td><td><a href='x.pdf'>pdf</a></td></tr>" + extra + "</table></html>")


class R:
    def __init__(self, status=200, text="", content=b""):
        self.status_code, self.text, self.content = status, text, content


def fake(lst, pages, fail=()):
    calls = []

    def get(url, headers=None, timeout=None):
        calls.append(url)
        if url == w.LIST:
            return R(503) if "list" in fail else R(200, lst)
        code = url.rsplit("/", 1)[-1]
        if code in fail:
            return R(500)
        return R(200, pages.get(code, "<html></html>"))
    return get, calls


class Thai(unittest.TestCase):
    def test_list_parse_and_wanted(self):
        rows = w.parse_list(listing(B1044, B1212, B2322, B1058))
        self.assertEqual([r["code"] for r in rows], ["AD1044", "AD1212", "AD2322", "AD1058"])
        r = rows[1]
        self.assertEqual((r["product"], r["type"], r["applies"], r["date"], r["status"]), (TIN, "AD", True, "2026-11-11", "ใช้มาตรการและอยู่ระหว่างการทบทวน"))
        self.assertIn(KR, r["countries"])
        self.assertFalse(rows[2]["applies"])                                    # 인도가 태국산에 건 조치는 보지 않는다
        self.assertEqual([w.wanted(x) for x in rows], [True, True, False, False])  # 페놀 수지(한국 없음)도 아님

    def test_case_page(self):
        p = w.parse_case(case_page([("A1", BOND)]))
        self.assertEqual((p["koreaRate"], p["dutyFrom"], p["dutyTo"]), ("0-22.67", ["2026-11-11", "2026-11-13"], "2027-11-12"))
        self.assertEqual(p["announcements"], [{"url": "https://thaitr.dft.go.th/storage/announcements/A1.pdf", "title": BOND}])
        self.assertEqual(p["steps"][-1], {"no": "1.1", "label": "เปิดไต่สวน", "dates": ["2020-04-07"], "pdf": "https://thaitr.dft.go.th/x.pdf"})

    def test_baseline_then_new_announcement_with_beat_name_is_a(self):
        pages = {"AD1044": case_page([("C1", BOND.replace(TIN, CHROME))]), "AD1212": case_page([("T1", BOND)])}
        get, calls = fake(listing(B1044, B1212, B2322, B1058), pages)
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        self.assertEqual((doc["events"], doc["status"], doc["checks"][0]["korea"]), ([], "ok", 2))
        self.assertEqual(sorted(c["code"] for c in doc["cases"]), ["AD1044", "AD1212"])
        self.assertNotIn(w.CASE + "AD1058", calls)
        # 다음 실행: AD1212 목록 날짜가 바뀌고 재심 개시 공고가 붙음 — AD1044는 그대로(다시 안 읽음)
        pages2 = {**pages, "AD1212": case_page([("T2", REVIEW), ("T1", BOND)])}
        get2, calls2 = fake(listing(B1212.replace("11 พ.ย. 2569", "20 พ.ย. 2569"), B1044, B2322), pages2)
        with mock.patch.object(w, "pdf_names", return_value=(["KG스틸"], 3)) as pn:
            doc2 = w.run(NOW + dt.timedelta(hours=5), doc, get=get2, sleep=lambda s: None)
        self.assertEqual(calls2, [w.LIST, w.CASE + "AD1212"])
        pn.assert_called_once()
        self.assertEqual(len(doc2["events"]), 1)
        e = doc2["events"][0]
        self.assertEqual((e["tier"], e["kind"], e["companies"], e["product"], e["date"], e["code"], e["korea"]),
                         ("A", "태국 무역구제(재심 개시)", ["KG스틸"], "석도강판", "2026-11-20", "AD1212", True))
        self.assertEqual(e["url"], "https://thaitr.dft.go.th/storage/announcements/T2.pdf")
        self.assertIn("태국 무역구제 공고 AD1212 — 재심 개시: 「ประกาศคณะกรรมการ", e["text"])
        self.assertIn("(석도강판) · 원산지 สาธารณรัฐประชาชนจีน", e["text"])
        self.assertIn("· 한국 세율 0-22.67%(CIF 기준, 사건 쪽 표) · 징수 2026-11-11, 2026-11-13~2027-11-12 · 공고 본문(PDF)에 출입처 KG스틸", e["text"])
        # 같은 상태로 또 돌면 아무것도 안 읽는다
        get3, calls3 = fake(listing(B1212.replace("11 พ.ย. 2569", "20 พ.ย. 2569"), B1044), pages2)
        self.assertEqual(len(w.run(NOW + dt.timedelta(hours=8), doc2, get=get3, sleep=lambda s: None)["events"]), 1)
        self.assertEqual(calls3, [w.LIST])
        # 품목 한국어 이름은 다시 안 읽어도 새 규칙으로 고친다(운영 11-19: 스테인리스 냉연이 '냉연강판'으로 저장됨)
        doc2["cases"][0]["productKo"] = "냉연강판"
        get4, _ = fake(listing(B1212.replace("11 พ.ย. 2569", "20 พ.ย. 2569"), B1044), pages2)
        self.assertEqual(next(c for c in w.run(NOW + dt.timedelta(hours=9), doc2, get=get4, sleep=lambda s: None)["cases"] if c["code"] == "AD1212")["productKo"], "석도강판")

    def test_new_case_on_list_is_event_even_when_deferred(self):
        get, _ = fake(listing(B1044, B1212), {"AD1044": case_page([("C1", BOND)]), "AD1212": case_page([("T1", BOND)])})
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        hr = block("AD1300", "เหล็กแผ่นรีดร้อน", KR, "อยู่ระหว่างการไต่สวน", "AD", "ไทยใช้มาตรการ", "19 พ.ย. 2569")
        # 새 사건은 처음 실행에서 한도로 못 읽음(사건 쪽 실패) → 다음 실행에서 읽어도 기준선이 아니다
        get2, _ = fake(listing(hr, B1044, B1212), {}, fail=("AD1300",))
        doc2 = w.run(NOW + dt.timedelta(hours=3), doc, get=get2, sleep=lambda s: None)
        self.assertEqual((doc2["status"], doc2["events"]), ("partial", []))
        self.assertTrue(next(c for c in doc2["cases"] if c["code"] == "AD1300")["newCase"])
        get3, _ = fake(listing(hr, B1044, B1212), {"AD1300": case_page([("H1", INIT)], rate="5.5")})
        with mock.patch.object(w, "pdf_names", return_value=([], 2)):
            e = w.run(NOW + dt.timedelta(hours=6), doc2, get=get3, sleep=lambda s: None)["events"][0]
        self.assertEqual((e["tier"], e["kind"], e["product"], e["companies"]), ("A", "태국 무역구제(조사 개시)", "열연강판", []))   # 한국산 출입 업종 품목 개시
        self.assertIn("공고 본문(PDF)에 출입처 영문 이름 없음", e["text"])

    def test_page_budget_keeps_old_date_so_next_run_rereads(self):
        get, _ = fake(listing(B1044, B1212), {"AD1044": case_page([("C1", BOND)]), "AD1212": case_page([("T1", BOND)])})
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        with mock.patch.object(w, "PAGE_BUDGET", 0):
            get2, calls2 = fake(listing(B1212.replace("11 พ.ย. 2569", "20 พ.ย. 2569"), B1044), {})
            doc2 = w.run(NOW + dt.timedelta(hours=3), doc, get=get2, sleep=lambda s: None)
        self.assertEqual(calls2, [w.LIST])
        self.assertEqual(next(c for c in doc2["cases"] if c["code"] == "AD1212")["date"], "2026-11-11")
        get3, calls3 = fake(listing(B1212.replace("11 พ.ย. 2569", "20 พ.ย. 2569"), B1044), {"AD1212": case_page([("T2", REVIEW), ("T1", BOND)])})
        with mock.patch.object(w, "pdf_names", return_value=([], 2)):
            doc3 = w.run(NOW + dt.timedelta(hours=6), doc2, get=get3, sleep=lambda s: None)
        self.assertEqual([e["kind"] for e in doc3["events"]], ["태국 무역구제(재심 개시)"])
        self.assertEqual(doc3["events"][0]["tier"], "B")                         # 출입처 이름 없는 재심 개시

    def test_new_step_row_is_event(self):
        # 탐침 23: '관련 공고' 칸에는 가장 최근 공고만 — 재심 개시 고시는 조사 단계 표의 새 줄로 붙는다
        get, _ = fake(listing(B1044), {"AD1044": case_page([("C1", BOND)])})
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        get2, _ = fake(listing(B1044.replace("11 พ.ย. 2569", "21 พ.ย. 2569")), {"AD1044": case_page([("C1", BOND)], extra=STEP_REVIEW)})
        with mock.patch.object(w, "pdf_names", return_value=(["KG스틸"], 2)) as pn:
            evs = w.run(NOW + dt.timedelta(hours=3), doc, get=get2, sleep=lambda s: None)["events"]
        pn.assert_called_once_with(mock.ANY, "https://thaitr.dft.go.th/storage/steps/R21.pdf")
        self.assertEqual([(e["kind"], e["tier"], e["url"]) for e in evs], [("태국 무역구제(재심 개시)", "A", "https://thaitr.dft.go.th/storage/steps/R21.pdf")])

    def test_old_parser_cases_are_reread_once_without_events(self):
        get, _ = fake(listing(B1044), {"AD1044": case_page([("C1", BOND)])})
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        doc["cases"][0].pop("parser")
        doc["cases"][0].pop("koreaRate")
        get2, calls2 = fake(listing(B1044), {"AD1044": case_page([("C1", BOND)])})
        doc2 = w.run(NOW + dt.timedelta(hours=3), doc, get=get2, sleep=lambda s: None)
        self.assertEqual((calls2, doc2["events"], doc2["cases"][0]["koreaRate"], doc2["cases"][0]["parser"]), ([w.LIST, w.CASE + "AD1044"], [], "0-22.67", w.PARSER))
        get3, calls3 = fake(listing(B1044), {})
        w.run(NOW + dt.timedelta(hours=6), doc2, get=get3, sleep=lambda s: None)
        self.assertEqual(calls3, [w.LIST])

    def test_list_failure_keeps_previous(self):
        get, _ = fake(listing(B1044), {"AD1044": case_page([("C1", BOND)])})
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        get2, _ = fake("", {}, fail=("list",))
        doc2 = w.run(NOW + dt.timedelta(hours=3), doc, get=get2, sleep=lambda s: None)
        self.assertEqual((doc2["status"], len(doc2["cases"]), doc2["stale"]), ("failed", 1, True))
        get3, _ = fake("<html>점검 중</html>", {})
        self.assertIn("형식 변경 의심", w.run(NOW, None, get=get3, sleep=lambda s: None)["checks"][0]["error"])

    def test_list_connection_error_is_retried_once(self):
        state, waits = {"n": 0}, []

        def get(url, headers=None, timeout=None):
            if url == w.LIST:
                state["n"] += 1
                if state["n"] == 1:
                    raise ConnectionError("HTTPSConnectionPool(host='thaitr.dft.go.th', port=443): Max retries exceeded")
                return R(200, listing(B1044))
            return R(200, "<html></html>")
        doc = w.run(NOW, None, get=get, sleep=waits.append)
        self.assertEqual((doc["status"], state["n"]), ("ok", 2))
        self.assertIn(w.LIST_RETRY_WAIT, waits)
        get2, calls = fake(listing(B1044), {}, fail=("list",))       # 503 두 번이면 실패(0건 아님)
        doc2 = w.run(NOW, None, get=get2, sleep=lambda s: None)
        self.assertEqual((doc2["status"], calls.count(w.LIST)), ("failed", 2))

        def bad(url, headers=None, timeout=None):
            raise ValueError("parse")
        with self.assertRaises(ValueError):                           # 연결 문제가 아닌 오류는 다시 받지 않는다
            w.get_list(bad, lambda s: None)

    def test_kinds_dates_products(self):
        self.assertEqual(w.kind_of(BOND), "담보 요구")
        self.assertEqual(w.kind_of(REVIEW), "재심 개시")
        self.assertEqual(w.kind_of(INIT), "조사 개시")
        self.assertEqual(w.kind_of("ประกาศ เรื่อง ยุติการไต่สวน"), "조사 종료")
        # AD1004 단계 표(운영 11-19)
        self.assertEqual(w.kind_of("รายละเอียดข้อมูลและข้อเท็จจริงที่ใช้เป็นพื้นฐานในการพิจารณาร่างผลการทบทวนฯ (ฉบับเปิดเผย)"), "예비 결과 공개")
        self.assertEqual(w.kind_of("ประกาศคณะกรรมการ ทตอ. เรื่อง ผลการทบทวนความจำเป็นในการใช้มาตรการตอบโต้การทุ่มตลาดสินค้าเหล็กกล้าไร้สนิมรีดเย็น"), "재심 결과")
        self.assertEqual(w.kind_of("ประกาศกรมการค้าต่างประเทศ เปิดการทบทวน"), "재심 개시")
        seg = ("<td>อากรที่เรียกเก็บ</td><td>1. ประเทศญี่ปุ่น 1.1 JFE Steel Corporation เรียกเก็บในอัตราร้อยละ 19.82 ของราคา ซี ไอ เอฟ "
               "3. สาธารณรัฐเกาหลี เรียกเก็บในอัตราร้อยละ 50.99 ของราคา ซี ไอ เอฟ</td><td>อากรร้อยละ 0</td>")
        self.assertEqual(w.parse_case(seg)["koreaRate"], "50.99")
        self.assertEqual(w.th_date("วันที่ : 07 เม.ย. 2563"), "2020-04-07")
        self.assertEqual(w.th_date("31 ธ.ค. 2569"), "2026-12-31")
        self.assertEqual(w.product_ko(CHROME)[0], "크롬도금강판")
        self.assertEqual(w.product_ko("เหล็กกล้าไร้สนิมรีดเย็น ชนิดม้วน แผ่น และแผ่นแถบ")[0], "스테인리스강")   # AD1004(운영 11-19)
        self.assertEqual(w.product_ko("ฟีโนลิกเรซิน"), (None, []))


if __name__ == "__main__":
    unittest.main()
