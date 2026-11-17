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
            if url == w.API + w.AUDIT:
                return Resp(NO)
            return Resp(content=b"<html>error</html>", status=500)
        doc = None
        for k in range(3):
            doc = w.run(NOW, doc, key="k", get=get, sleep=lambda s: None, extract=extract)
            self.assertEqual(doc["status"], "partial")
            self.assertIn("회의록 57701:ValueError", doc["checks"][0]["error"])
        self.assertIn("57701", doc["seen"])          # 세 번째에 넘김
        self.assertNotIn("57701", doc.get("tries", {}))

    def test_api_down_is_failed_not_zero(self):
        doc = w.run(NOW, None, key="k", get=lambda *a, **k: (_ for _ in ()).throw(TimeoutError()), sleep=lambda s: None, extract=extract)
        self.assertEqual(doc["status"], "failed")

    def test_kia_after_hyundai_and_particle_safe_terms(self):
        rx = [r for c, r in w.TERMS if c == "기아"][-1]
        self.assertTrue(rx.search("현대차·기아 노조가"))
        self.assertFalse(any(r.search("기아 문제와 빈곤") for c, r in w.TERMS if c == "기아"))


if __name__ == "__main__":
    unittest.main()
