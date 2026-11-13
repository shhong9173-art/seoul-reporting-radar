"""자동차리콜센터 무상점검·수리 게시판 감시: 목록·상세 파서(11-13·11-14 탐침에서 본 꼴), 출입처 가르기, 기준선, 새 글, 등급, 실패 때 직전 상태."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import kr_free_repair as f  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 14, 6, 10, tzinfo=KST)


class Resp:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status


def list_page(posts, n, total):
    rows = "".join(
        f"""<li><a href="#none" onclick="$main.event.detailView('{no}','O');">\n<strong>{title}</strong></a>
        <ol><li>국토교통부</li><li>{date}</li><li>조회수 : 286</li></ol></li>""" for no, title, date in posts[(n - 1) * 5:n * 5])
    return f"<html><body><p>전체 {total:,}건 (페이지 {n}/836)</p><ul class=\"board-hrznt-list\">{rows}</ul></body></html>"


def detail_page(maker, model, units, reason, produced="2021-04-23 ~ 2024-08-12"):
    return f"""<table><tbody>
    <tr><th scope="row">제작(수입)사</th><td>{maker}</td><th scope="row">차명</th><td>{model}</td></tr>
    <tr><th scope="row">생산기간</th><td>{produced}</td><th scope="row">무상수리기간</th><td>2026-11-12 ~</td></tr>
    <tr><th scope="row">대수</th><td>{units}</td><th scope="row">기타문의</th><td>080-200-2000</td></tr>
    <tr><th scope="row">무상점검내용</th><td colspan="3">{reason}</td></tr>
    <tr><th scope="row">조치사항</th><td colspan="3">소프트웨어 업데이트</td></tr></tbody></table>
    <a href="#none" onclick="fileDownload('12','1')">무상수리 안내문.pdf</a>"""


class Site:
    """가짜 게시판. posts는 최신순 (글 번호, 제목, 날짜), 쪽마다 5건."""

    def __init__(self, posts, details=None, robots=Resp("<html><body>404</body></html>", 404), fail_list=None, fail_detail=()):
        self.posts, self.details, self.robots = posts, details or {}, robots
        self.fail_list, self.fail_detail = fail_list, set(fail_detail)
        self.pages, self.opened = [], []

    def get(self, url, headers=None, timeout=None):
        if url == f.ROBOTS:
            if isinstance(self.robots, Exception):
                raise self.robots
            return self.robots
        return self._list(1)

    def post(self, url, data=None, headers=None, timeout=None):
        if url == f.LIST:
            return self._list(int(data["currentPageNo"]))
        self.opened.append(data["gratischeckId"])
        if data["gratischeckId"] in self.fail_detail:
            return Resp("", 500)
        return Resp(self.details.get(data["gratischeckId"], detail_page("기아(주)", "차", "120 대", "경고등 점등")))

    def _list(self, n):
        self.pages.append(n)
        if self.fail_list:
            return Resp("", self.fail_list)
        return Resp(list_page(self.posts, n, 4177))


def posts(first, count, date="2026-11-01"):
    return [(str(first - i), f"[포르쉐] 카이엔 - 부품 {i} 관련 무상수리", date) for i in range(count)]


OLD = posts(4870, 20)
K8 = ("4874", "[기아] K8 HEV - HPCU 관련 무상수리", "2026-11-13")
TASMAN = ("4875", "[기아] 타스만 - BDC 관련 무상수리", "2026-11-12")
OLD_HYUNDAI = ("4871", "[현대] 아반떼 - 계기판 관련 무상수리", "2026-11-05")
DETAILS = {"4874": detail_page("기아(주)", "K8(GL3) HEV", "77,043 대", "HPCU 소프트웨어 설계 오류로 경고등이 점등될 가능성"),
           "4875": detail_page("기아(주)", "타스만(TK1)", "1,204 대", "BDC 소프트웨어 오류로 실내등이 꺼지지 않을 가능성"),
           "4871": detail_page("현대자동차(주)", "아반떼(CN7)", "3,300 대", "계기판 표시 오류")}


def nosleep(_):
    return None


class Parsers(unittest.TestCase):
    def test_list_and_detail_shapes(self):
        rows, total = f.parse_list(list_page([K8, TASMAN], 1, 4177))
        self.assertEqual(total, 4177)
        self.assertEqual(rows[0], {"id": "4874", "ctype": "O", "title": "[기아] K8 HEV - HPCU 관련 무상수리", "source": "국토교통부", "date": "2026-11-13"})
        d = f.parse_detail(DETAILS["4874"])
        self.assertEqual((d["maker"], d["model"], d["units"], d["produced"]), ("기아(주)", "K8(GL3) HEV", 77043, "2021-04-23 ~ 2024-08-12"))
        self.assertIn("HPCU 소프트웨어 설계 오류", d["reason"])
        self.assertEqual(d["action"], "소프트웨어 업데이트")
        self.assertEqual(d["attach"], ["무상수리 안내문.pdf"])
        self.assertEqual(f.parse_list("<html>점검 중</html>"), ([], None))

    def test_beat_brands_only(self):
        for title, want in (("[기아] K8 HEV - HPCU 관련 무상수리", "기아"), ("[현대] 팰리세이드 - ABS 관련 무상수리", "현대차"),
                            ("[제네시스] GV80 - 후방카메라 관련 무상수리", "현대차"), ("[비엠더블유] 520i - 냉각수 관련 무상수리", "BMW코리아"),
                            ("[한국지엠] 트랙스 - 변속기 관련 무상수리", "한국GM"), ("[케이지모빌리티] 토레스 - 무상수리", "KG모빌리티"),
                            ("[벤츠] E클래스 - 무상수리", "메르세데스-벤츠 코리아"), ("[아우디] A6 - 무상수리", "아우디코리아")):
            self.assertEqual(f.brand_of(title), want, title)
        # 출입처가 아닌 브랜드·이름에 '현대'가 든 다른 회사
        for title in ("[포르쉐] 카이엔 - 무상수리", "[볼보] XC60 - 무상수리", "[테슬라] 모델 Y - 무상수리", "[현대건설기계] 지게차 - 무상수리", "[BYD] 아토3 - 무상수리"):
            self.assertIsNone(f.brand_of(title), title)
        # 제목 머리말이 모호하면 상세의 제작사 칸으로
        self.assertEqual(f.brand_of("[국산] 쏘렌토 - 무상수리", "기아(주)"), "기아")

    def test_tiers(self):
        self.assertEqual(f.classify({"company": "기아", "units": 77043, "title": "", "reason": ""})[0], "A")
        self.assertEqual(f.classify({"company": "현대차", "units": 900, "title": "[현대] 넥쏘 - 무상수리", "reason": "주행 중 시동 꺼짐 가능성"})[0], "A")
        self.assertEqual(f.classify({"company": "기아", "units": 1204, "title": "[기아] 타스만 - BDC 관련 무상수리", "reason": "실내등이 꺼지지 않을 가능성"})[0], "B")
        self.assertEqual(f.classify({"company": None, "units": 500000, "title": "[포르쉐] 화재", "reason": "화재"})[0], "C")


class Collect(unittest.TestCase):
    def test_first_run_is_baseline_except_last_two_days(self):
        site = Site([K8, TASMAN, OLD_HYUNDAI] + OLD, DETAILS)
        sec, check = f.collect(None, NOW, site, sleep=nosleep)
        self.assertEqual(check["status"], "ok")
        self.assertEqual((check["pages"], check["returned"], check["total"]), (4, 20, 4177))
        self.assertEqual((check["newPosts"], check["newBeat"]), (2, 2))
        by = {x["no"]: x for x in sec["items"]}
        self.assertTrue(by["4874"]["isNew"] and not by["4874"]["baseline"])
        self.assertEqual((by["4874"]["tier"], by["4874"]["units"], by["4874"]["company"]), ("A", 77043, "기아"))
        self.assertEqual(by["4875"]["tier"], "B")
        # 열흘 전 현대차 글: 기준선(새 항목 아님)이지만 상세는 읽어 둔다
        self.assertTrue(by["4871"]["baseline"] and not by["4871"]["isNew"])
        self.assertEqual((by["4871"]["units"], by["4871"]["company"]), (3300, "현대차"))
        # 출입처 아닌 글은 상세를 열지 않는다
        self.assertEqual(sorted(site.opened), ["4871", "4874", "4875"])
        self.assertEqual(by["4870"]["tier"], "C")
        # 글마다 주소가 겹치지 않는다(처리 장부가 주소로 가리기 때문)
        self.assertEqual(by["4874"]["url"], "https://www.car.go.kr/ri/grts/list.do#4874")
        self.assertEqual(len({x["url"] for x in sec["items"]}), len(sec["items"]))

    def test_next_run_reads_only_until_seen_and_announces_new_posts(self):
        base = [TASMAN, OLD_HYUNDAI] + OLD
        first, _ = f.collect(None, NOW, Site(base, DETAILS), sleep=nosleep)
        site = Site([K8] + base, DETAILS)
        sec, check = f.collect(first, NOW + dt.timedelta(hours=5), site, sleep=nosleep)
        self.assertEqual(site.pages, [1, 2])          # 2쪽이 본 글뿐이라 거기서 멈춤
        self.assertEqual((check["newPosts"], check["newBeat"], check["detailsRead"]), (1, 1, 1))
        by = {x["no"]: x for x in sec["items"]}
        self.assertTrue(by["4874"]["isNew"])
        self.assertFalse(by["4875"]["isNew"])         # 지난 실행의 새 글은 이제 새 글 아님
        self.assertFalse(by["4875"]["baseline"])      # 그래도 기준선 글로 바뀌지는 않는다
        again, check2 = f.collect(sec, NOW + dt.timedelta(hours=8), Site([K8] + base, DETAILS), sleep=nosleep)
        self.assertEqual((check2["newPosts"], check2["pages"]), (0, 1))
        self.assertEqual(len(again["items"]), len(sec["items"]))

    def test_failures_keep_previous_and_are_not_zero(self):
        first, _ = f.collect(None, NOW, Site([TASMAN] + OLD, DETAILS), sleep=nosleep)
        sec, check = f.collect(first, NOW + dt.timedelta(hours=5), Site([K8, TASMAN] + OLD, fail_list=500), sleep=nosleep)
        self.assertEqual(check["status"], "failed")
        self.assertIn("목록 1쪽 HTTP 500", check["error"])
        self.assertTrue(sec["stale"])
        self.assertEqual(len(sec["items"]), len(first["items"]))
        none, check0 = f.collect(None, NOW, Site([], fail_list=503), sleep=nosleep)
        self.assertIsNone(none)
        self.assertEqual(check0["status"], "failed")
        # 정상 응답인데 글이 한 줄도 없으면 형식 변경 의심 — 0건으로 넘기지 않는다
        _, empty = f.collect(first, NOW + dt.timedelta(hours=5), Site([]), sleep=nosleep)
        self.assertEqual(empty["status"], "failed")
        self.assertIn("형식 변경 의심", empty["error"])

    def test_detail_failure_is_retried_and_budget_overflow_waits(self):
        base = [TASMAN] + OLD
        first, _ = f.collect(None, NOW, Site(base, DETAILS), sleep=nosleep)
        sec, check = f.collect(first, NOW + dt.timedelta(hours=5), Site([K8] + base, DETAILS, fail_detail=["4874"]), sleep=nosleep)
        k8 = next(x for x in sec["items"] if x["no"] == "4874")
        self.assertEqual((k8["detail"], k8["tier"], k8["company"]), ("failed", "B", "기아"))   # 대수를 못 읽었으면 A로 올리지 않는다
        sec2, _ = f.collect(sec, NOW + dt.timedelta(hours=8), Site([K8] + base, DETAILS), sleep=nosleep)
        k8 = next(x for x in sec2["items"] if x["no"] == "4874")
        self.assertEqual((k8["detail"], k8["tier"], k8["units"]), ("ok", "A", 77043))
        # 한 번에 출입처 새 글이 한도보다 많으면 나머지는 다음 실행으로
        many = [(str(5000 - i), f"[기아] 차종 {i} - 무상수리", "2026-11-14") for i in range(15)]
        sec3, check3 = f.collect(first, NOW + dt.timedelta(hours=5), Site(many + base), sleep=nosleep)
        self.assertEqual((check3["detailsRead"], check3["pending"]), (f.DETAIL_BUDGET, 3))
        sec4, check4 = f.collect(sec3, NOW + dt.timedelta(hours=8), Site(many + base), sleep=nosleep)
        self.assertEqual((check4["detailsRead"], check4["pending"], check4["newPosts"]), (3, 0, 0))

    def test_robots_rules(self):
        base = [TASMAN] + OLD
        blocked = Site(base, robots=Resp("User-agent: *\nDisallow: /ri/\n"))
        sec, check = f.collect(None, NOW, blocked, sleep=nosleep)
        self.assertIsNone(sec)
        self.assertEqual((check["status"], blocked.pages), ("failed", []))      # 막혀 있으면 목록을 부르지 않는다
        self.assertIn("robots.txt가 이 게시판 경로를 막음", check["error"])
        slow = Site(base, robots=Resp("User-agent: *\nCrawl-delay: 86400\n"))
        self.assertEqual(f.collect(None, NOW, slow, sleep=nosleep)[1]["status"], "failed")
        down = Site(base, robots=ConnectionError("x"))
        self.assertIn("robots.txt 확인 실패", f.collect(None, NOW, down, sleep=nosleep)[1]["error"])
        ok = Site(base, DETAILS, robots=Resp("User-agent: *\nDisallow: /adm/\n"))
        self.assertEqual(f.collect(None, NOW, ok, sleep=nosleep)[1]["robots"], "robots.txt 허용")
        self.assertEqual(f.collect(None, NOW, Site(base, DETAILS), sleep=nosleep)[1]["robots"], "robots.txt 없음")


if __name__ == "__main__":
    unittest.main()
