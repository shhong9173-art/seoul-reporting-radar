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
        self.assertEqual(len(doc2["notices"]), 3)

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
