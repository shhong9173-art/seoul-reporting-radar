"""노동위원회 회의 일정: 11-03 탐침 130~135 실제 응답 글자(첫 화면 '오늘 회의' 칸의 data-* 속성, 회의 상세의 담당 사건정보)로
회의·사건 나누기, 사건명 앞 당사자와 출입처 규칙(공장등록 accept 재사용, 계열사·이름 겹침 제외), A/B, 5건 상한 표시, 본 회의 다시 안 읽기,
조회 실패는 0이 아니라 미확인."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import kr_labor_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 3, 8, 35, tzinfo=KST)


def meeting_tag(slug, mid, ymd, cd, label):
    path = f"/nlrc/{slug}/meetingSche/detail.do" if slug else "/nlrc/meetingSche/detail.do"
    return (f'<li><a href="javascript:;" class="sche" data-action="{path}" data-nlrc-event="click-submit" data-mtg-id="{mid}" '
            f'data-mtg-sn="1" data-mtg-ymd="{ymd}" data-cmit-cd="{cd}" ><span class="tag">{label}</span> 심판정 14:00</a></li>')


def detail_html(cmit, name, place, day, start, rows):
    body = "".join(f"<tr><td>{no}</td><td class='left'>{case}</td><td>{tm}</td></tr>" for no, case, tm in rows)
    return (f"<html><body><nav>소식 공지사항 회의일정</nav><h3>회의일정 정보</h3><table><tr><th>관할위원회</th><td>{cmit}</td></tr>"
            f"<tr><th>회의명</th><td>{name}</td></tr><tr><th>회의장소</th><td>{place}</td></tr><tr><th>회의일자</th><td>{day}</td></tr>"
            f"<tr><th>회의시간</th><td>{start} ~ 17:00</td></tr><tr><th>담당위원</th><td>김갑,이을</td></tr></table>"
            f"<h4>담당 사건정보</h4><table><thead><tr><th>사건번호</th><th>사건명</th><th>회의시간</th></tr></thead><tbody>{body}</tbody></table>"
            f"<a href='#'>목록</a><footer>전체메뉴 찾아오시는 길</footer></body></html>")


# 11-03 탐침 131 실제 사건명(경북·중앙·전남) + 출입처 시험용 사건
GYEONGBUK = detail_html("경북", "1차조정회의", "조정회의실", "2026-11-03", "14:00",
                        [("2026조정87", "에스케이실트론 주식회사 노동쟁의 조정신청사건", "14:00"),
                         ("2026조정88", "주식회사 포스코 노동쟁의 조정신청사건", "15:00")])
CENTRAL = detail_html("중앙", "심판회의", "1심판정", "2026-11-03", "13:00",
                      [("2026부해716", "지에스건설 주식회사 부당정직 구제 재심신청", "15:30"),
                       ("2026부해846", "주식회사 케이티엠앤에스 부당희망퇴직거부 구제 재심신청", "15:30"),
                       ("2026부해900", "현대자동차 주식회사 부당해고 구제 재심신청", "16:00"),
                       ("2026부노41", "현대제철 주식회사 외 1 부당노동행위 구제 재심신청", "16:30")])
JEONNAM = detail_html("전남", "심판회의", "심판정", "2026-11-03", "13:30",
                      [("2026부해882", "한일 연합의원 부당해고 구제신청", "16:00"),
                       ("2026부해886", "주식회사 페퍼저축은행 (PEPPER SAVINGS BANK) 부당해고 구제신청", "14:00")])


class R:
    def __init__(self, status=200, text=""):
        self.status_code, self.text = status, text


def site(fail=(), five=False):
    calls = []
    mains = {
        "https://www.nlrc.go.kr/": meeting_tag("", "2611011300000000001", "20261103", "00", "심판")
        + ("".join(meeting_tag("", f"261101130000000000{i}", "20261103", "00", "심판") for i in range(5, 9)) if five else ""),
        "https://www.nlrc.go.kr/nlrc/gyeongbuk/main.do": meeting_tag("gyeongbuk", "2610151732500052964", "20261103", "06", "조정"),
        "https://www.nlrc.go.kr/nlrc/jeonnam/main.do": meeting_tag("jeonnam", "2610131635410063392", "20261103", "05", "심판"),
    }
    details = {"2611011300000000001": CENTRAL, "2610151732500052964": GYEONGBUK, "2610131635410063392": JEONNAM}
    empty = detail_html("중앙", "심판회의", "2심판정", "2026-11-03", "14:00", [])

    def get(url, timeout=None):
        calls.append(url)
        if any(f in url for f in fail):
            raise type("ConnectTimeout", (Exception,), {})("x")
        if "meetingSche/detail.do" in url:
            mid = url.split("mtgId=")[1].split("&")[0]
            return R(200, details.get(mid, empty))
        if url.endswith("/main.do") or url == "https://www.nlrc.go.kr/":
            return R(200, "<html>" + mains.get(url, "<p>금일 회의가 없습니다.</p>") + "</html>")
        return R(404, "nf")
    return get, calls


class Parse(unittest.TestCase):
    def test_meetings_and_detail_cases_from_real_layout(self):
        ms = w.meetings_of(meeting_tag("gyeongbuk", "2610151732500052964", "20261103", "06", "조정"))
        self.assertEqual(ms, [{"action": "/nlrc/gyeongbuk/meetingSche/detail.do", "mtgId": "2610151732500052964", "mtgSn": "1",
                               "mtgYmd": "20261103", "cmitCd": "06", "label": "조정"}])
        self.assertEqual(w.detail_url(ms[0]), "https://www.nlrc.go.kr/nlrc/gyeongbuk/meetingSche/detail.do?mtgId=2610151732500052964&mtgSn=1&mtgYmd=20261103&cmitCd=06")
        d = w.parse_detail(CENTRAL)
        self.assertEqual((d["commission"], d["meeting"], d["day"], d["start"]), ("중앙", "심판회의", "2026-11-03", "13:00"))
        self.assertEqual([c["no"] for c in d["cases"]], ["2026부해716", "2026부해846", "2026부해900", "2026부노41"])
        self.assertEqual(d["cases"][1]["name"], "주식회사 케이티엠앤에스 부당희망퇴직거부 구제 재심신청")
        self.assertIsNone(w.parse_detail("<html>Error 죄송합니다. 해당 페이지를 찾을 수 없습니다.</html>"))   # POST 오류 쪽(11-03 탐침 131)

    def test_party_and_beat_rules(self):
        self.assertEqual(w.party_of("현대자동차 주식회사 부당해고 구제 재심신청"), "현대자동차 주식회사")
        self.assertEqual(w.norm_party("주식회사 페퍼저축은행 (PEPPER SAVINGS BANK)"), "페퍼저축은행")
        self.assertEqual(w.norm_party("현대제철 주식회사 외 1"), "현대제철")
        self.assertEqual(w.beat_of("주식회사 포스코 노동쟁의 조정신청사건"), "포스코")
        self.assertEqual(w.beat_of("현대제철 주식회사 외 1 부당노동행위 구제 재심신청"), "현대제철")
        self.assertEqual(w.beat_of("기아 주식회사 부당해고 구제신청"), "기아")
        self.assertEqual(w.beat_of("에스케이이노베이션 주식회사 노동쟁의 조정신청사건"), "SK이노베이션")
        # 계열사·이름 겹침은 출입처가 아니다
        self.assertIsNone(w.beat_of("에스케이실트론 주식회사 노동쟁의 조정신청사건"))
        self.assertIsNone(w.beat_of("주식회사 포스코이앤씨 부당해고 구제신청"))
        self.assertIsNone(w.beat_of("현대자동차써비스 주식회사 부당해고 구제신청"))
        self.assertIsNone(w.beat_of("지에스건설 주식회사 부당정직 구제 재심신청"))
        self.assertIsNone(w.beat_of("효성중공업 주식회사 부당해고 구제신청"))   # (관련) 회사는 뺀다
        self.assertEqual(w.tier_of("주식회사 포스코 노동쟁의 조정신청사건", "1차조정회의"), "A")
        self.assertEqual(w.tier_of("현대제철 주식회사 외 1 부당노동행위 구제 재심신청", "심판회의"), "A")
        self.assertEqual(w.tier_of("현대자동차 주식회사 부당해고 구제 재심신청", "심판회의"), "B")


class Run(unittest.TestCase):
    def test_events_for_beat_cases_and_seen_meetings_not_reread(self):
        get, calls = site()
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        self.assertEqual(doc["status"], "complete")
        self.assertEqual(len(doc["checks"]), 14)
        ev = {e["caseNo"]: e for e in doc["events"]}
        self.assertEqual(sorted(ev), ["2026부노41", "2026부해900", "2026조정88"])
        self.assertEqual((ev["2026조정88"]["company"], ev["2026조정88"]["tier"], ev["2026조정88"]["kind"]), ("포스코", "A", "노동위 조정 회의"))
        self.assertEqual((ev["2026부노41"]["tier"], ev["2026부노41"]["kind"]), ("A", "노동위 심판 회의"))
        self.assertEqual(ev["2026부해900"]["tier"], "B")
        self.assertEqual([ev[k]["word"] for k in ("2026조정88", "2026부노41", "2026부해900")], ["노동쟁의", "부당노동행위", "부당해고"])
        self.assertIn("경북지방노동위원회 1차조정회의 2026-11-03 15:00 · 사건 2026조정88 「주식회사 포스코 노동쟁의 조정신청사건」", ev["2026조정88"]["text"])
        self.assertIn("사건명은 신청 주장", ev["2026조정88"]["text"])
        self.assertTrue(ev["2026조정88"]["url"].startswith("https://www.nlrc.go.kr/nlrc/gyeongbuk/meetingSche/detail.do?mtgId="))
        self.assertEqual(doc["counts"], {"meetings": 3, "details": 3, "cases": 8, "조정 사건": 2})
        self.assertNotIn("김갑", str(doc))   # 위원 이름은 저장하지 않는다
        # 다시 돌면 본 회의 상세는 다시 안 읽고 이벤트도 늘지 않는다
        get2, calls2 = site()
        doc2 = w.run(NOW + dt.timedelta(hours=5), doc, get=get2, sleep=lambda s: None)
        self.assertFalse([u for u in calls2 if "detail.do" in u])
        self.assertEqual(len(doc2["events"]), 3)
        self.assertEqual(doc2["counts"], {"meetings": 3, "details": 3, "cases": 8, "조정 사건": 2})   # 같은 날은 이어 센다
        doc3 = w.run(NOW + dt.timedelta(days=1), doc2, get=site()[0], sleep=lambda s: None)
        self.assertEqual(doc3["counts"]["cases"], 0)   # 다음 날은 새로(본 회의는 다시 안 읽음)
        self.assertEqual(len(doc2["notices"]), 3)

    def test_same_case_next_meeting_is_alerted_again_with_prior_dates(self):
        # 조정은 1차·2차 회의가 따로 열리고 마지막 회의에서 조정 중지·성립이 난다 — 같은 사건번호가 다른 날 다시 나오면 다시 알리고 앞선 회의 날짜를 붙인다
        doc = w.run(NOW, None, get=site()[0], sleep=lambda s: None)
        later = detail_html("경북", "2차조정회의", "조정회의실", "2026-11-10", "10:00", [("2026조정88", "주식회사 포스코 노동쟁의 조정신청사건", "10:00")])
        other = detail_html("전남", "1차조정회의", "조정회의실", "2026-11-10", "10:00", [("2026조정88", "주식회사 포스코 노동쟁의 조정신청사건", "11:00")])

        def get(url, timeout=None):
            if "meetingSche/detail.do" in url:
                return R(200, later if "mtgId=2611" in url and "cmitCd=06" in url else other)
            if url.endswith("/gyeongbuk/main.do"):
                return R(200, "<html>" + meeting_tag("gyeongbuk", "2611091200000000001", "20261110", "06", "조정") + "</html>")
            if url.endswith("/jeonnam/main.do"):   # 다른 위원회의 같은 번호는 다른 사건
                return R(200, "<html>" + meeting_tag("jeonnam", "2611091200000000002", "20261110", "05", "조정") + "</html>")
            return R(200, "<html><p>금일 회의가 없습니다.</p></html>")
        doc2 = w.run(NOW + dt.timedelta(days=7), doc, get=get, sleep=lambda s: None)
        new = [e for e in doc2["events"] if e["detectedAt"] == doc2["generatedAt"]]
        again = [e for e in new if e["commission"] == "경북지방노동위원회"]
        self.assertEqual(len(again), 1)
        self.assertEqual((again[0]["tier"], again[0]["kind"], again[0]["prior"]), ("A", "노동위 조정 회의 (같은 사건 다시)", ["2026-11-03"]))
        self.assertIn("2차조정회의 2026-11-10 10:00 · 사건 2026조정88", again[0]["text"])
        self.assertTrue(again[0]["text"].endswith("· 같은 사건 앞선 회의 11-03"))
        n = next(x for x in doc2["notices"] if x["id"] == again[0]["id"])
        self.assertEqual(n["prior"], ["2026-11-03"])
        jn = [e for e in new if e["commission"] == "전남지방노동위원회"]
        self.assertEqual((len(jn), "prior" in jn[0], jn[0]["kind"]), (1, False, "노동위 조정 회의"))

    def test_calendar_from_reporter_browser_reads_beyond_widget_and_ahead(self):
        # 11-04: 기자 컴퓨터 브라우저 달력 수집(kr-labor-browser) — 5건 상한 밖 회의와 미리 잡힌 회의를 읽는다
        base, calls = site()
        ahead = detail_html("경북", "2차조정회의", "조정회의실", "2026-11-10", "10:00", [("2026조정88", "주식회사 포스코 노동쟁의 조정신청사건", "10:00")])
        extra = detail_html("경북", "심판회의", "심판정", "2026-11-03", "16:00", [("2026부해950", "현대제철 주식회사 부당해고 구제신청", "16:00")])
        judge = detail_html("경북", "심판회의", "심판정", "2026-11-05", "10:00", [("2026부해951", "한일 연합의원 부당해고 구제신청", "10:00")])

        def get(url, timeout=None):
            if "mtgId=2611101000000000001" in url:
                calls.append(url)
                return R(200, ahead)
            if "mtgId=2611031600000000001" in url:
                calls.append(url)
                return R(200, extra)
            if "mtgId=2611051000000000001" in url:
                calls.append(url)
                return R(200, judge)
            return base(url, timeout)
        stamp = NOW.isoformat()
        row = lambda mid, ymd, title: {"mtgId": mid, "mtgSn": "1", "mtgYmd": ymd, "cmitCd": "06", "title": title}  # noqa: E731
        browser = {"schema": "kr_labor_browser/v1", "commissions": [
            {"commission": "경북지방노동위원회", "fetchedAt": stamp, "rows": [
                row("2610151732500052964", "20261103", "조정회의"),      # 첫 화면 칸과 같은 회의 — 한 번만 읽는다
                row("2611031600000000001", "20261103", "심판회의"),      # 첫 화면 칸 밖 오늘 회의
                row("2611051000000000001", "20261105", "심판회의"),
                row("2611101000000000001", "20261110", "2차조정회의"),   # 미리 잡힌 조정회의
                row("2612011000000000001", "20261201", "심판회의"),      # 14일 넘게 뒤 — 안 읽음
                {"mtgId": "../x", "mtgSn": "1", "mtgYmd": "20261104", "cmitCd": "06"}]},
            {"commission": "서울지방노동위원회", "fetchedAt": stamp, "rows": [], "error": "TypeError: Failed to fetch"}]}
        w.DETAIL_BUDGET, keep = 1, w.DETAIL_BUDGET
        try:
            doc = w.run(NOW, None, get=get, sleep=lambda s: None, browser=browser)
        finally:
            w.DETAIL_BUDGET = keep
        read = [u.split("mtgId=")[1].split("&")[0] for u in calls if "detail.do" in u]
        self.assertEqual(read.count("2610151732500052964"), 1)
        self.assertIn("2611031600000000001", read)                 # 오늘 회의는 상한과 상관없이 다 읽는다
        self.assertIn("2611101000000000001", read)                 # 앞으로 회의 1건 상한 — 조정회의가 먼저
        self.assertNotIn("2611051000000000001", read)
        self.assertNotIn("2612011000000000001", read)
        self.assertEqual((doc["calendar"]["left"], doc["calendar"]["meetings"], doc["calendar"]["status"]), (1, 4, "partial"))
        self.assertIn("서울지방노동위원회", doc["calendar"]["missing"])
        ev = {e["caseNo"]: e for e in doc["events"]}
        self.assertEqual(ev["2026부해950"]["company"], "현대제철")
        fut = [e for e in doc["events"] if e["id"] == "labor:06:2026조정88:2026-11-10"][0]
        self.assertEqual((fut["tier"], fut["ahead"], fut["prior"]), ("A", 7, ["2026-11-03"]))
        self.assertEqual(fut["kind"], "노동위 조정 회의 (미리 잡힌 회의) (같은 사건 다시)")
        self.assertIn("2차조정회의 2026-11-10 10:00 · 사건 2026조정88", fut["text"])
        self.assertIn("· 미리 잡힌 회의(7일 뒤, 달력) · 같은 사건 앞선 회의 11-03", fut["text"])
        self.assertEqual(doc["seen"]["06:2611101000000000001:1"], "20261110@20261103")
        gb = next(c for c in doc["checks"] if c["source"] == "경북지방노동위원회")
        self.assertEqual((gb["returned"], gb["calendar"], "note" in gb), (1, 4, False))
        self.assertEqual(doc["counts"]["ahead"], 1)
        # 다음 날: 남은 회의(11-05)를 읽고, 미리 읽은 회의는 회의일 전이라 다시 안 읽는다
        calls.clear()
        doc2 = w.run(NOW + dt.timedelta(days=1), doc, get=get, sleep=lambda s: None, browser=browser)
        read2 = [u.split("mtgId=")[1].split("&")[0] for u in calls if "detail.do" in u]
        self.assertIn("2611051000000000001", read2)
        self.assertNotIn("2611101000000000001", read2)
        self.assertEqual(doc2["calendar"]["left"], 0)
        # 회의 당일: 한 번 더 읽되 같은 사건은 다시 알리지 않는다
        calls.clear()
        later = dict(browser, commissions=[dict(browser["commissions"][0], fetchedAt=(NOW + dt.timedelta(days=7)).isoformat())])
        doc3 = w.run(NOW + dt.timedelta(days=7), doc2, get=get, sleep=lambda s: None, browser=later)
        self.assertIn("2611101000000000001", [u.split("mtgId=")[1].split("&")[0] for u in calls if "detail.do" in u])
        self.assertEqual(doc3["seen"]["06:2611101000000000001:1"], "20261110")
        self.assertEqual(sum(1 for e in doc3["events"] if e["id"] == "labor:06:2026조정88:2026-11-10"), 1)

    def test_widget_failure_still_reads_calendar_meetings(self):
        base, calls = site(fail=("gyeongbuk/main.do",))
        browser = {"commissions": [{"commission": "경북지방노동위원회", "fetchedAt": NOW.isoformat(),
                                    "rows": [{"mtgId": "2610151732500052964", "mtgSn": "1", "mtgYmd": "20261103", "cmitCd": "06", "title": "조정회의"}]}]}
        doc = w.run(NOW, None, get=base, sleep=lambda s: None, browser=browser)
        gb = next(c for c in doc["checks"] if c["source"] == "경북지방노동위원회")
        self.assertEqual(gb["status"], "partial")
        self.assertIn("첫 화면 조회 실패(ConnectTimeout: x) — 달력 회의만 읽음", gb["error"])
        self.assertIn("2026조정88", {e["caseNo"] for e in doc["events"]})
        doc = w.run(NOW, None, get=site(fail=("gyeongbuk/main.do",))[0], sleep=lambda s: None)
        self.assertEqual(next(c for c in doc["checks"] if c["source"] == "경북지방노동위원회")["status"], "failed")

    def test_stale_or_missing_calendar_keeps_widget_cap_note(self):
        get, _ = site(five=True)
        old = {"commissions": [{"commission": "중앙노동위원회", "fetchedAt": (NOW - dt.timedelta(days=4)).isoformat(),
                                "rows": [{"mtgId": "2611101000000000009", "mtgSn": "1", "mtgYmd": "20261104", "cmitCd": "00"}]}]}
        doc = w.run(NOW, None, get=get, sleep=lambda s: None, browser=old)
        central = next(c for c in doc["checks"] if c["source"] == "중앙노동위원회")
        self.assertIn("note", central)
        self.assertEqual((doc["calendar"]["status"], doc["calendar"]["meetings"]), ("partial", 0))
        doc = w.run(NOW, None, get=site(five=True)[0], sleep=lambda s: None)
        self.assertEqual(doc["calendar"]["status"], "unset")

    def test_detail_read_is_retried_once(self):
        get, calls = site()
        flaky = {"n": 0}

        def get2(url, timeout=None):
            if "2610151732500052964" in url and flaky["n"] == 0:
                flaky["n"] += 1
                raise type("ReadTimeout", (Exception,), {})("x")
            return get(url, timeout=timeout)
        waits = []
        doc = w.run(NOW, None, get=get2, sleep=waits.append)
        self.assertIn("2026조정88", {e["caseNo"] for e in doc["events"]})
        self.assertIn(5.0, waits)
        self.assertEqual(doc["status"], "complete")

    def test_cap_and_failures_are_marked(self):
        get, _ = site(five=True, fail=("/nlrc/seoul/main.do",))
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        by = {c["source"]: c for c in doc["checks"]}
        self.assertIn("5건 상한", by["중앙노동위원회"]["note"])
        self.assertEqual(by["서울지방노동위원회"]["status"], "failed")
        self.assertEqual(doc["status"], "partial")
        get3, _ = site(fail=("nlrc.go.kr",))
        self.assertEqual(w.run(NOW, None, get=get3, sleep=lambda s: None)["status"], "failed")


if __name__ == "__main__":
    unittest.main()
