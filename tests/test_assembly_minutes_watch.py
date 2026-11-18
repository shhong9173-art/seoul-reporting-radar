import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import assembly_minutes_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 18, 9, 20, tzinfo=KST)


class Resp:
    def __init__(self, body=None, content=b"", status=200):
        self._b, self.content, self.status_code = body, content, status

    def json(self):
        return self._b


def committee_rows(day, rows):
    return {w.COMMITTEE: [{"head": [{"list_total_count": len(rows)}, {"RESULT": {"CODE": "INFO-000"}}]}, {"row": rows}]}


NO = {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}}
# 11-18 탐침에서 본 모양(산자중기위 11-09, 안건마다 한 줄) — 교육위는 지켜보지 않는다
ROWS_1109 = [
    {"CONFER_NUM": "57701", "TITLE": "제22대 제439회 제6차 산업통상자원중소벤처기업위원회 (2026년 11월 09일)", "COMM_NAME": "산업통상자원중소벤처기업위원회",
     "CONF_DATE": "2026-11-09", "SUB_NAME": "1. 2027년도 예산안", "PDF_LINK_URL": "https://record.assembly.go.kr/assembly/viewer/minutes/download/pdf.do?id=57701"},
    {"CONFER_NUM": "57701", "TITLE": "제22대 제439회 제6차 산업통상자원중소벤처기업위원회 (2026년 11월 09일)", "COMM_NAME": "산업통상자원중소벤처기업위원회",
     "CONF_DATE": "2026-11-09", "SUB_NAME": "2. 2027년도 기금운용계획안", "PDF_LINK_URL": "https://record.assembly.go.kr/assembly/viewer/minutes/download/pdf.do?id=57701"},
    {"CONFER_NUM": "57692", "TITLE": "제22대 제439회 제6차 교육위원회", "COMM_NAME": "교육위원회", "CONF_DATE": "2026-11-09", "SUB_NAME": "1. 예산안",
     "PDF_LINK_URL": "https://record.assembly.go.kr/assembly/viewer/minutes/download/pdf.do?id=57692"},
]
AUDIT_ROWS = {w.AUDIT: [{"head": [{"list_total_count": 2}]}, {"row": [
    {"CONF_ID": "N054585", "ERACO": "제22대", "SESS": "제439회", "DGR": "개회식", "CONF_DT": "2026-10-22", "CMIT_NM": "산업통상자원중소벤처기업위원회",
     "DOWN_URL": "https://record.assembly.go.kr/assembly/viewer/minutes/download/pdf.do?id=57437"},
    {"CONF_ID": "N054680", "ERACO": "제22대", "SESS": "제439회", "DGR": "개회식", "CONF_DT": "2026-10-28", "CMIT_NM": "성평등가족위원회",
     "DOWN_URL": "https://record.assembly.go.kr/assembly/viewer/minutes/download/pdf.do?id=57539"}]}]}

TEXT_57701 = ("◯위원장 이철규 의사일정 제1항을 상정합니다.\f"
              "◯김정호 위원 기술이 산업이 되려면 실증 인프라가 있어야 하고 현대자동차 그룹이 새만금에 9조 원을 투자하고 로봇클러스터에 4000억을 투입하는 데 "
              "있어서 공용 실증 인프라가 뒤따르지 못하면 효과는 반감됩니다. 그런 얘기 들어보셨습니까?\n"
              "◯산업통상부장관 김정관 예, 공감하고 있습니다. 현대제철 당진 공장의 가동 중단 문제는 회사와 협의하고 있습니다." + " 이하 생략." * 80)
TEXT_57437 = "◯증인 홍길동 포스코 광양제철소 화재 사고 경위를 말씀드리겠습니다." + " 이하 생략." * 100


def fake_get(urls):
    def get(url, params=None, headers=None, timeout=None):
        urls.append((url, dict(params or {})))
        assert "seoul-reporting-radar" in headers["User-Agent"]
        if url == w.API + w.COMMITTEE:
            return Resp(committee_rows(params["CONF_DATE"], ROWS_1109) if params["CONF_DATE"] == "2026-11-09" else NO)
        if url.startswith(w.API + "AUDITREPORT"):
            return Resp(NO)
        if url == w.API + w.APPENDIX:
            return Resp(NO)
        if url == w.API + w.AUDIT:
            assert params["ERACO"] == "제22대"
            return Resp(AUDIT_ROWS)
        if "id=57701" in url:
            return Resp(content=b"%PDF-1.4 57701")
        if "id=57437" in url:
            return Resp(content=b"%PDF-1.4 57437")
        raise AssertionError(f"뜻밖의 주소 {url}")
    return get


def extract(raw):
    return TEXT_57701 if b"57701" in raw else TEXT_57437


class AssemblyMinutesTest(unittest.TestCase):
    def test_unset_key_is_not_zero(self):
        doc = w.run(NOW, None, key="", get=lambda *a, **k: None)
        self.assertEqual(doc["status"], "not_configured")
        self.assertEqual(doc["checks"][0]["status"], "unset")

    def test_reads_watched_minutes_with_speaker_page_and_tiers(self):
        urls = []
        doc = w.run(NOW, None, key="k", get=fake_get(urls), sleep=lambda s: None, extract=extract)
        self.assertEqual(doc["status"], "complete")
        c = doc["checks"][0]
        self.assertEqual((c["meetings"], c["returned"], c["read"]), (2, 2, 2))     # 교육위·성평등가족위는 받지 않는다
        self.assertFalse(any("57692" in u or "57539" in u for u, _ in urls))
        self.assertEqual(sum(1 for u, _ in urls if u == w.API + w.COMMITTEE), w.LOOKBACK_DAYS)
        items = {x["id"]: x for x in doc["items"]}
        hy = items["nam:57701:현대차"]
        self.assertEqual(hy["tier"], "C")                     # 사건 낱말 없음
        self.assertTrue(hy["snippets"][0].startswith("2쪽 · 김정호 위원 · 기술이 산업이"))   # 앞 발언자 말은 자르고, 쪽은 \f로 센다
        self.assertEqual(hy["agenda"], "1. 2027년도 예산안 / 2. 2027년도 기금운용계획안")
        steel = items["nam:57701:현대제철"]
        self.assertEqual(steel["tier"], "A")                  # '가동 중단' + 회의일 14일 안
        self.assertIn("산업통상부장관 김정관", steel["snippets"][0])
        posco = items["nam:57437:포스코"]
        self.assertEqual((posco["tier"], posco.get("old"), posco["kind"]), ("C", True, "국정감사 회의록"))   # 화재·사고지만 옛 회의(10-22)
        ev = [e for e in doc["events"]]
        self.assertEqual([e["id"] for e in ev], ["nam:57701:현대제철"])
        self.assertIn("의원 질의는 주장", ev[0]["text"])
        # 다음 실행: 본 회의록은 다시 받지 않는다
        urls2 = []
        doc2 = w.run(NOW + dt.timedelta(days=1), doc, key="k", get=fake_get(urls2), sleep=lambda s: None, extract=extract)
        self.assertFalse(any("pdf.do" in u for u, _ in urls2))
        self.assertEqual(doc2["checks"][0]["returned"], 0)
        self.assertEqual(len(doc2["events"]), 1)

    def test_pdf_failure_retries_then_gives_up(self):
        def get(url, params=None, headers=None, timeout=None):
            if url == w.API + w.COMMITTEE:
                return Resp(committee_rows(params["CONF_DATE"], ROWS_1109) if params["CONF_DATE"] == "2026-11-09" else NO)
            if url.startswith(w.API + "AUDITREPORT"):
                return Resp(NO)
            if url == w.API + w.APPENDIX:
                return Resp(NO)
            if url == w.API + w.AUDIT:
                return Resp(NO)
            return Resp(content=b"<html>error</html>", status=500)
        doc = None
        for k in range(3):
            doc = w.run(NOW, doc, key="k", get=get, sleep=lambda s: None, extract=extract)
            self.assertEqual(doc["status"], "partial")
            self.assertIn("회의록 57701:ValueError(PDF 아님 HTTP 500)", doc["checks"][0]["error"])
        self.assertIn("57701", doc["seen"])          # 세 번째에 넘김
        self.assertNotIn("57701", doc.get("tries", {}))

    def test_not_posted_file_waits_without_counting_as_failure(self):
        # 11-18 첫 실행: 국정감사 회의록 12개가 파일 대신 '원본 회의록 파일이 등록되지 않았습니다' 알림을 돌려줬다
        alert = "<script type='text/javascript'>alert('내려받을 원본 회의록 파일이 등록되지 않았습니다.');history.back();</script>".encode("utf-8")
        def get(url, params=None, headers=None, timeout=None):
            if url == w.API + w.COMMITTEE:
                return Resp(committee_rows(params["CONF_DATE"], ROWS_1109) if params["CONF_DATE"] == "2026-11-09" else NO)
            if url.startswith(w.API + "AUDITREPORT"):
                return Resp(NO)
            if url == w.API + w.APPENDIX:
                return Resp(NO)
            if url == w.API + w.AUDIT:
                return Resp(AUDIT_ROWS)
            if "id=57437" in url:
                return Resp(content=alert)
            return Resp(content=b"%PDF-1.4 57701")
        prev = {"schema": w.SCHEMA, "tries": {"57437": 1}}
        doc = w.run(NOW, prev, key="k", get=get, sleep=lambda s: None, extract=extract)
        c = doc["checks"][0]
        self.assertEqual((doc["status"], c["notPosted"], c["opened"], c["read"]), ("complete", 1, 1, 1))
        self.assertNotIn("57437", doc["seen"])
        self.assertNotIn("57437", doc.get("tries", {}))
        self.assertNotIn("error", c)

    def test_budget_counts_only_real_files(self):
        old = w.DETAIL_BUDGET
        try:
            w.DETAIL_BUDGET = 1
            urls = []
            doc = w.run(NOW, None, key="k", get=fake_get(urls), sleep=lambda s: None, extract=extract)
            c = doc["checks"][0]
            self.assertEqual((c["opened"], c["pending"]), (1, 1))
        finally:
            w.DETAIL_BUDGET = old

    def test_mando_needs_hl_or_context_and_old_items_are_rechecked(self):
        rx = [r for c, r in w.TERMS if c == "HL만도"][0]
        self.assertFalse(rx.search("AIDC만도 18.4GW, 2035년도까지 준공하겠다"))      # 11-18 첫 실행
        self.assertFalse(rx.search("그것만도 어렵습니다"))
        self.assertTrue(rx.search("HL만도 평택공장 하청노동자"))
        self.assertTrue(rx.search("만도 평택공장에서"))
        bad = {"id": "nam:57378:HL만도", "company": "HL만도", "snippets": ["51쪽 · 어기구 위원 · AIDC만도 18.4GW"], "tier": "C", "firstSeen": "2026-11-18T01:56:00+09:00"}
        ok = {"id": "nam:57375:HL만도", "company": "HL만도", "snippets": ["102쪽 · 서왕진 위원 · HL만도 평택공장 하청노동자"], "tier": "C", "firstSeen": "2026-11-18T01:56:00+09:00"}
        prev = {"schema": w.SCHEMA, "rulesV": w.RULES_V, "items": [bad, ok], "events": [{"id": "nam:57378:HL만도", "tier": "A", "detectedAt": "2026-11-18T01:56:00+09:00"}],
                "seen": {"57701": "20261109", "57437": "20261022"}}
        doc = w.run(NOW, prev, key="k", get=fake_get([]), sleep=lambda s: None, extract=extract)
        ids = {x["id"] for x in doc["items"]}
        self.assertNotIn("nam:57378:HL만도", ids)
        self.assertIn("nam:57375:HL만도", ids)
        self.assertEqual(doc["events"], [])

    def test_line_breaks_inside_names(self):
        # 11-18 첫 실행: PDF 줄 끝에서 낱말 가운데가 끊겨 '포스코이\n앤씨'(계열사)가 포스코로 잡혔다
        rx = dict((c, r) for c, r in w.TERMS)
        text = "◯정일영 위원 왜 포스코이\n앤씨가 문제가 되냐면 산재가 600명입니다. ◯산업통상부장관 김정관 현대제\n철 당진 공장의 가동\n중단 문제는 협의하고 있습니다. 포스코는 수소환원제철을"
        self.assertEqual([text[a:b] for a, b in w.name_spans(text, rx["포스코"])], ["포스코"])     # 끝의 '포스코는'만
        spans = w.name_spans(text, rx["현대제철"])
        self.assertEqual([text[a:b] for a, b in spans], ["현대제\n철"])
        snips, near = w.hits(text, rx["현대제철"])
        self.assertTrue(near)                       # '가동\n중단'도 사건 낱말
        self.assertIn("산업통상부장관 김정관 · 현대제 철 당진", snips[0])

    def test_rules_change_rereads_seen_minutes_once(self):
        urls = []
        prev = {"schema": w.SCHEMA, "seen": {"57701": "20261109", "57437": "20261022"},
                "items": [{"id": "nam:57437:포스코", "company": "포스코", "snippets": ["11쪽 · 정일영 위원 · 포스코이 앤씨가"], "firstSeen": "2026-11-18T01:56:00+09:00"}]}
        doc = w.run(NOW, prev, key="k", get=fake_get(urls), sleep=lambda s: None, extract=extract)   # 앞 판(rulesV 없음)
        self.assertEqual(doc["rulesV"], w.RULES_V)
        self.assertEqual(sum(1 for u, _ in urls if "pdf.do" in u), 2)
        posco = next(x for x in doc["items"] if x["id"] == "nam:57437:포스코")
        self.assertNotIn("앤씨", posco["snippets"][0])        # 앞 판 대목은 버리고 다시 읽은 대목
        self.assertIn("광양제철소 화재", posco["snippets"][0])
        urls2 = []
        w.run(NOW, doc, key="k", get=fake_get(urls2), sleep=lambda s: None, extract=extract)
        self.assertFalse(any("pdf.do" in u for u, _ in urls2))

    def test_written_answers_appendix(self):
        # 11-18 탐침: 국정감사 회의록마다 부록 '[서면질의·답변서]' PDF(2025 산자중기위 154MB·963쪽). 2026년 것은 아직 안 올라옴
        apx_rows = {w.APPENDIX: [{"head": [{"list_total_count": 1}]}, {"row": [
            {"CONF_KND": "국정감사", "ERACO": "제22대", "SESS": "제439회", "DGR": "개회식", "CONF_DT": "20261022        ", "CONF_ID": "N054585", "FILE_KND": "부록",
             "FILE_CN": "[서면질의·답변서]", "DOWN_URL": "https://record.assembly.go.kr/assembly/mnts/apdix/apdixDownload.do?fileId=150001", "CONFER_NUM": "57437"}]}]}
        text = ("2026년도 국정감사 산업통상자원중소벤처기업위원회회의록 (부록) 【서면질의】 ◯강승규 위원 ····· 1\f"
                "2026.10.22 산업통상부 국감 서면질의서 (박형수 의원) 01 철강 산업 지원 현황 E 현대제철 당진 전기로 가동 중단 이후 협력업체 대책은? "
                "- 회사와 협의 중임\f" + "답 변 이하 생략. " * 300 +
                "2026.10.22 산업통상부 국감 서면질의서 (김원이 의원) 포스코 수소환원제철 실증 일정은? - 2030년 상용화 목표" + " 이하." * 50)
        calls, fetched = [], []
        def get(url, params=None, headers=None, timeout=None, stream=None):
            calls.append((url, dict(params or {})))
            if url == w.API + w.COMMITTEE:
                return Resp(NO)
            if url == w.API + w.AUDIT:
                return Resp(AUDIT_ROWS)
            if url.startswith(w.API + "AUDITREPORT"):
                return Resp(NO)
            if url == w.API + w.APPENDIX:
                return Resp(apx_rows if params["CONF_ID"] == "N054585" else NO)
            if "pdf.do" in url:
                return Resp(content=b"%PDF-1.4 57437")
            raise AssertionError(url)
        fetch = lambda u: fetched.append(u) or "tok"
        doc = w.run(NOW, None, key="k", get=get, sleep=lambda s: None, extract=extract, apx_fetch=fetch, apx_extract=lambda tok: text)
        c = doc["checks"][0]
        self.assertEqual(doc["status"], "complete")
        self.assertEqual(c["appendix"], {"meetings": 1, "asked": 1, "posted": 1, "new": 1, "read": 1, "pending": 0})   # 성평등가족위 국정감사는 묻지 않음
        self.assertEqual(fetched, ["https://record.assembly.go.kr/assembly/mnts/apdix/apdixDownload.do?fileId=150001"])
        items = {x["id"]: x for x in doc["items"]}
        steel = items["nap:150001:현대제철"]
        self.assertEqual((steel["tier"], steel["kind"], steel["date"]), ("A", "국정감사 서면질의·답변서", "20261022"))   # 회의 27일 뒤라도 처음 공개 문서 — A
        self.assertTrue(steel["snippets"][0].startswith("2쪽 · 박형수 의원 서면질의(산업통상부) · "))
        posco = items["nap:150001:포스코"]
        self.assertEqual(posco["tier"], "C")
        self.assertIn("김원이 의원 서면질의(산업통상부)", posco["snippets"][0])
        self.assertEqual(sorted(e["id"] for e in doc["events"]), ["nap:150001:현대제철", "napdoc:150001"])
        ev = {e["id"]: e for e in doc["events"]}
        self.assertIn("서면질의는 의원 주장, 답변은 기관 설명", ev["nap:150001:현대제철"]["text"])
        # 올라온 것 자체를 알리는 B 한 줄(대목이 C뿐이어도)
        self.assertEqual(ev["napdoc:150001"]["tier"], "B")
        self.assertRegex(ev["napdoc:150001"]["text"], r"^산업통상자원중소벤처기업위원회 국정감사\(2026-10-22\) 서면질의·답변서가 올라옴 — 3쪽 · 출입처 대목 2곳\((?:현대제철·포스코|포스코·현대제철)\) · 사건 낱말 가까이 현대제철")
        # 다음 실행: 읽은 부록이 있는 회의는 부록 API를 다시 묻지 않고, 부록도 다시 받지 않는다
        calls.clear(); fetched.clear()
        doc2 = w.run(NOW + dt.timedelta(days=1), doc, key="k", get=get, sleep=lambda s: None, extract=extract, apx_fetch=fetch, apx_extract=lambda tok: text)
        self.assertFalse(any(u == w.API + w.APPENDIX for u, _ in calls))
        self.assertEqual(fetched, [])
        self.assertEqual(doc2["checks"][0]["appendix"]["posted"], 1)
        self.assertIn("nap:150001:현대제철", {x["id"] for x in doc2["items"]})

    def test_written_answers_budget_and_failures(self):
        rows = [{"CONF_ID": f"N0546{i}", "ERACO": "제22대", "SESS": "제439회", "CONF_DT": "2026-10-2" + str(i), "CMIT_NM": "정무위원회",
                 "DOWN_URL": f"https://record.assembly.go.kr/assembly/viewer/minutes/download/pdf.do?id=5760{i}"} for i in range(3)]
        audit = {w.AUDIT: [{"head": [{"list_total_count": 3}]}, {"row": rows}]}
        def get(url, params=None, headers=None, timeout=None, stream=None):
            if url == w.API + w.COMMITTEE:
                return Resp(NO)
            if url == w.API + w.AUDIT:
                return Resp(audit)
            if url.startswith(w.API + "AUDITREPORT"):
                return Resp(NO)
            if url == w.API + w.APPENDIX:
                i = params["CONF_ID"][-1]
                return Resp({w.APPENDIX: [{"head": [{"list_total_count": 1}]}, {"row": [{"FILE_CN": "[서면질의·답변서]",
                             "DOWN_URL": f"https://record.assembly.go.kr/assembly/mnts/apdix/apdixDownload.do?fileId=16000{i}"}]}]})
            return Resp(content=b"%PDF-1.4 x")
        def fetch(u):
            if u.endswith("160002"):     # 가장 최근 회의(먼저 받는다)
                raise TimeoutError()
            return u
        doc = w.run(NOW, None, key="k", get=get, sleep=lambda s: None, extract=extract, apx_fetch=fetch, apx_extract=lambda u: "현대차 공장 증설 계획" * 300)
        a = doc["checks"][0]["appendix"]
        self.assertEqual((a["new"], a["read"], a["pending"]), (3, 1, 1))    # 실패 1 + 읽음 1 = 상한 2, 나머지 1은 다음 실행
        self.assertEqual(doc["status"], "partial")
        self.assertIn("부록 받기 160002:TimeoutError", doc["checks"][0]["error"])
        self.assertEqual(set(doc["apxSeen"]), {"160001"})
        self.assertEqual(doc["apxTries"], {"160002": 1})
        self.assertEqual(doc["apxDone"], ["N05461"])

    def test_apx_download_streams_to_file(self):
        class Stream:
            def __init__(self, body, status=200):
                self.body, self.status_code = body, status
            def iter_content(self, n):
                for i in range(0, len(self.body), 7):
                    yield self.body[i:i + 7]
        path = w.apx_download("u", lambda url, headers=None, timeout=None, stream=None: Stream(b"%PDF-1.6 hello world"))
        with open(path, "rb") as f:
            self.assertEqual(f.read(), b"%PDF-1.6 hello world")
        import os
        os.unlink(path)
        alert = "<script>alert('내려받을 원본 회의록 파일이 등록되지 않았습니다.');</script>".encode("utf-8")
        with self.assertRaisesRegex(ValueError, "^아직$"):
            w.apx_download("u", lambda url, headers=None, timeout=None, stream=None: Stream(alert))
        old = w.APX_MAX
        try:
            w.APX_MAX = 10
            with self.assertRaisesRegex(ValueError, "파일이 큼"):
                w.apx_download("u", lambda url, headers=None, timeout=None, stream=None: Stream(b"%PDF-1.6 " + b"x" * 40))
        finally:
            w.APX_MAX = old

    def test_apx_who_skips_committee_names(self):
        text = "【피감기관】 ◯최저임금위원회 ◯중앙노동위원회 ·········· 36쪽 현대차 협력사 납품"
        self.assertEqual(w.apx_who(text, text.index("현대차"))[0], "서면질의(의원 미상)")
        text = "◯강승규 위원 ····· 2025.10.29 중소벤처기업부 국감 서면질의서 (박형수 의원) 현대차"
        self.assertEqual(w.apx_who(text, text.index("현대차"))[0], "박형수 의원 서면질의(중소벤처기업부)")
        text = "◯김 위원장 ◯강승규 위원 현대차"
        self.assertEqual(w.apx_who(text, text.index("현대차"))[0], "강승규 의원 서면질의")

    def test_audit_result_reports_baseline_then_new(self):
        # 11-18 탐침: 결과보고서 358건·처리결과보고서 960건, 칸 RPT_YR·CMIT_NM·RPT_TTL·PDF_DWLD_URL·HWP_DWLD_URL
        base = "https://likms.assembly.go.kr/inspection/result/2025/pdf/"
        res = [{"RPT_YR": "2025", "CMIT_NM": "정무위원회", "RPT_TTL": "2025년도 국정감사 결과보고서()", "PDF_DWLD_URL": base + "000631588.PDF"},
               {"RPT_YR": "2025", "CMIT_NM": "행정안전위원회", "RPT_TTL": "2025년도 국정감사 결과보고서()", "PDF_DWLD_URL": base + "000631589.PDF"}]
        vis = [{"RPT_YR": "2025", "CMIT_NM": "정무위원회", "RPT_TTL": "2025년도 국정감사결과 시정 및 처리요구사항에 대한 처리결과보고서(금융위원회)", "PDF_DWLD_URL": base + "000631622.PDF"}]
        lists = {"AUDITREPORTRESULT": res, "AUDITREPORTVISIBILITY": vis}
        def get(url, params=None, headers=None, timeout=None, stream=None):
            for code, rows in lists.items():
                if url == w.API + code:
                    return Resp({code: [{"head": [{"list_total_count": len(rows)}]}, {"row": rows}]})
            if url in (w.API + w.COMMITTEE, w.API + w.AUDIT, w.API + w.APPENDIX):
                return Resp(NO)
            raise AssertionError(url)
        fetched = []
        def fetch(u):
            fetched.append(u)
            if u.endswith("000640001.PDF"):
                raise ValueError("PDF 아님 HTTP 200")   # 목록에는 있는데 파일 대신 HTML
            return u
        text = "Ⅲ. 처리결과 1. 산업통상부 현대제철 당진 전기로 가동 중단에 따른 협력업체 지원 대책 마련 요구 — 처리결과: 지원 방안 검토 중" + " 이하 생략." * 200
        doc = w.run(NOW, None, key="k", get=get, sleep=lambda s: None, extract=extract, apx_fetch=fetch, apx_extract=lambda u: text)
        r = doc["checks"][0]["reports"]
        self.assertEqual((r["listed"], r["baseline"], r["new"]), (2, 2, 0))     # 첫 실행은 기준선 — 행정안전위는 안 봄
        self.assertEqual(fetched, [])
        self.assertTrue(doc["repBase"])
        # 이튿날: 산자중기위 처리결과보고서(산업통상부)가 새로 올라옴 + 파일이 아직 안 열리는 것 하나
        vis.append({"RPT_YR": "2025", "CMIT_NM": "산업통상자원중소벤처기업위원회", "RPT_TTL": "2025년도 국정감사결과 시정 및 처리요구사항에 대한 처리결과보고서(산업통상부)", "PDF_DWLD_URL": base + "000640000.PDF"})
        vis.append({"RPT_YR": "2025", "CMIT_NM": "국토교통위원회", "RPT_TTL": "2025년도 국정감사결과 시정 및 처리요구사항에 대한 처리결과보고서(국토교통부)", "PDF_DWLD_URL": base + "000640001.PDF"})
        doc2 = w.run(NOW + dt.timedelta(days=1), doc, key="k", get=get, sleep=lambda s: None, extract=extract, apx_fetch=fetch, apx_extract=lambda u: text)
        r2 = doc2["checks"][0]["reports"]
        self.assertEqual((r2["new"], r2["read"], r2["waiting"]), (2, 1, 1))
        self.assertEqual(doc2["status"], "complete")
        item = {x["id"]: x for x in doc2["items"]}["nar:000640000:현대제철"]
        self.assertEqual((item["tier"], item["kind"]), ("A", "국정감사 처리결과보고서"))
        self.assertTrue(item["snippets"][0].startswith("1쪽 · 처리결과보고서(산업통상부) · "))
        ev = {e["id"]: e for e in doc2["events"]}
        self.assertEqual(ev["nardoc:000640000"]["tier"], "B")
        self.assertIn("2025년도 국정감사결과 시정 및 처리요구사항에 대한 처리결과보고서(산업통상부) 올라옴 — 1쪽 · 출입처 대목 1곳(현대제철)", ev["nardoc:000640000"]["text"])
        self.assertEqual(doc2["repWait"], {"000640001": "2026-11-19"})
        # 30일 지나도 안 열리면 넘긴다
        later = w.run(NOW + dt.timedelta(days=31), doc2, key="k", get=get, sleep=lambda s: None, extract=extract, apx_fetch=fetch, apx_extract=lambda u: text)
        self.assertIn("000640001", later["repSeen"])
        self.assertIn("보고서 받기 000640001:파일이 30일 넘게 안 열림(넘김)", later["checks"][0]["error"])

    def test_audit_reports_list_failure_keeps_baseline_pending(self):
        def get(url, params=None, headers=None, timeout=None, stream=None):
            if url.startswith(w.API + "AUDITREPORT"):
                raise TimeoutError()
            return Resp(NO)
        doc = w.run(NOW, None, key="k", get=get, sleep=lambda s: None, extract=extract)
        self.assertFalse(doc["repBase"])          # 목록을 못 읽었으면 기준선을 아직 잡지 않는다(다음 실행이 기준선)
        self.assertEqual(doc["status"], "partial")

    def test_api_down_is_failed_not_zero(self):
        doc = w.run(NOW, None, key="k", get=lambda *a, **k: (_ for _ in ()).throw(TimeoutError()), sleep=lambda s: None, extract=extract)
        self.assertEqual(doc["status"], "failed")

    def test_kia_after_hyundai_and_particle_safe_terms(self):
        rx = [r for c, r in w.TERMS if c == "기아"][-1]
        self.assertTrue(rx.search("현대차·기아 노조가"))
        self.assertFalse(any(r.search("기아 문제와 빈곤") for c, r in w.TERMS if c == "기아"))


if __name__ == "__main__":
    unittest.main()
