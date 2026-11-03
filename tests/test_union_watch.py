"""노조 성명·보도자료: 11-03 탐침 148 실제 그누보드 모양(금속노조 ce_B12 목록 줄·글의 <title>·bo_v_info 작성일·bo_v_con, 화섬식품노조
갤러리 목록)으로 글 번호·제목·시각·본문, 출입처 이름 규칙(포스코퓨처엠 제외·기아 지부), A/B·본문에만 있으면 한 단계 내림, 첫 실행 기준선,
본 글 다시 안 읽음, 글 읽기 실패는 다음 실행에 다시, 게시판 실패는 미확인."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import union_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 3, 21, 30, tzinfo=KST)


def kmwu_list(ids):
    rows = "".join(f'<tr class=""> <td class="td_subject"> <a href="https://kmwu.kr/bbs/board.php?bo_table=ce_B12&amp;wr_id={i}"> 제목 {i} </a> </td> <td class="td_date">2026-11-03</td> </tr>' for i in ids)
    return ('<table> <tbody> <tr class="bo_notice"> <td class="td_subject"> <a href="https://kmwu.kr/bbs/board.php?bo_table=ce_B12&amp;wr_id=219977"> 금속노조 관련 보도 참조사항 </a> </td>'
            '<td class="td_date">2025-06-05</td> </tr>' + rows + "</tbody></table>")


def kctfu_list(bo, ids):
    return '<ul id="team_ul">' + "".join(f'<li class="gall_li "> <a href="https://kctfu.org/bbs/board.php?bo_table={bo}&amp;wr_id={i}" class="gall_img"></a>'
                                          f'<div class="gall_txt"><a href="https://kctfu.org/bbs/board.php?bo_table={bo}&amp;wr_id={i}" class="gall_li_tit"> 글 {i} </a></div></li>' for i in ids) + "</ul>"


def kmwu_post(title, body, when="26-11-03 14:12"):
    return (f"<html><head><title>{title} &gt; 보도자료/성명 | 전국금속노동조합</title></head><body><section id=\"bo_v_info\"> 페이지 정보 작성자 대변인 "
            f"작성일 {when} 조회 12회 </section><section id=\"bo_v_atc\"><div id=\"bo_v_con\"><p>{body}</p></div></section></body></html>")


def kctfu_post(title, body, when="26-11-03 21:34"):
    return (f"<html><body><h2 id=\"bo_v_title\"><span class=\"bo_v_cate\">보도자료</span> {title} </h2><div id=\"bo_v_info\" class=\"flex\"> 작성자 교선국장 "
            f"작성일 {when} 0 조회수 1 </div><div id=\"bo_v_con\">{body}</div></body></html>")


POSTS = {
    ("ce_B12", "220888"): kmwu_post("[보도자료] 현대위아 특수사업부 노동자들, 일방적 분할 매각 중단 촉구", "금속노조 현대위아지회는 3일 특수사업부 분할 매각 계획 철회를 요구했다."),
    ("ce_B12", "220887"): kmwu_post("[보도자료] 금호타이어 광주공장 끼임 사고 노동자 중상", "금호타이어 광주공장에서 2일 밤 노동자가 설비에 끼이는 사고가 났다."),
    ("ce_B12", "220886"): kmwu_post("[성명] 노동절 집회 안내", "전국 각 지부가 참여한다. 포스코퓨처엠 지회도 함께한다."),
    ("ce_B12", "220885"): kmwu_post("[성명] 원청 교섭 거부 규탄", "현대제철 비정규직지회는 원청 현대제철이 교섭을 거부하고 있다고 밝혔다."),
    ("bodo", "469"): kctfu_post("LG화학지회, 성과급 기준 공개 요구", "화섬식품노조 LG화학지회는 회사에 성과급 산정 기준 공개를 요구했다."),
}


class R:
    def __init__(self, status=200, text=""):
        self.status_code, self.text = status, text


def fake(lists, posts=POSTS, fail=()):
    calls = []

    def get(url, params=None, headers=None, timeout=None):
        bo, wid = params.get("bo_table"), params.get("wr_id")
        calls.append((bo, wid))
        if bo in fail or (bo, wid) in fail:
            raise type("ConnectTimeout", (Exception,), {})("x")
        if wid:
            return R(200, posts[(bo, wid)])
        return R(200, lists[bo])
    return get, calls


class Parse(unittest.TestCase):
    def test_list_and_post(self):
        self.assertEqual(w.list_ids(kmwu_list(["220888", "220887"]), "ce_B12"), ["219977", "220888", "220887"])
        self.assertEqual(w.list_ids(kctfu_list("bodo", ["469", "468"]), "bodo"), ["469", "468"])
        p = w.parse_post(POSTS[("ce_B12", "220888")])
        self.assertEqual((p["title"], p["date"]), ("[보도자료] 현대위아 특수사업부 노동자들, 일방적 분할 매각 중단 촉구", "2026-11-03T14:12:00+09:00"))
        self.assertTrue(p["body"].startswith("금속노조 현대위아지회는 3일"))
        q = w.parse_post(POSTS[("bodo", "469")])
        self.assertEqual((q["title"], q["date"]), ("LG화학지회, 성과급 기준 공개 요구", "2026-11-03T21:34:00+09:00"))

    def test_names_and_tiers(self):
        self.assertEqual(w.beats_in("포스코퓨처엠 지회"), [])
        self.assertEqual(w.beats_in("포스코 노사, 임단협 본교섭 재개"), ["포스코"])
        self.assertEqual(w.beats_in("기아지부 조합원 정보 유출"), ["기아"])
        self.assertEqual(w.beats_in("기아대책 후원"), [])
        self.assertEqual(w.beats_in("영풍 석포제련소 노동자"), ["영풍"])
        self.assertEqual(w.tier_of("현대위아 분할 매각 중단 촉구", "", True), "A")
        self.assertEqual(w.tier_of("성과급 기준 공개 요구", "", True), "B")
        self.assertEqual(w.tier_of("원청 교섭 거부 규탄", "", False), "B")   # 이름이 본문에만 — A→B


class Run(unittest.TestCase):
    def test_baseline_then_new_posts(self):
        lists = {"ce_B12": kmwu_list(["220884"]), "bodo": kctfu_list("bodo", ["468"]), "news": kctfu_list("news", ["972"])}
        get, calls = fake(lists)
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        self.assertEqual(doc["status"], "complete")
        self.assertFalse([c for c in calls if c[1]])   # 기준선은 글을 열지 않는다
        self.assertEqual([c.get("note") for c in doc["checks"]], ["첫 실행 기준선"] * 3)
        lists2 = {"ce_B12": kmwu_list(["220888", "220887", "220886", "220885", "220884"]), "bodo": kctfu_list("bodo", ["469", "468"]), "news": kctfu_list("news", ["972"])}
        get2, calls2 = fake(lists2)
        doc2 = w.run(NOW + dt.timedelta(hours=3), doc, get=get2, sleep=lambda s: None)
        self.assertNotIn(("ce_B12", "220884"), calls2)   # 본 글은 다시 안 읽음
        ev = {e["id"]: e for e in doc2["events"]}
        self.assertEqual(sorted((e["company"], e["tier"]) for e in ev.values()),
                         [("LG화학", "B"), ("금호타이어", "A"), ("현대위아", "A"), ("현대제철", "B")])
        wia = ev["un:ce_B12:220888"]
        self.assertIn("금속노조 보도자료/성명 「[보도자료] 현대위아 특수사업부 노동자들, 일방적 분할 매각 중단 촉구」(2026-11-03 14:12)", wia["text"])
        self.assertIn("노조 발표(한쪽 주장) — 회사 입장·사실관계 확인", wia["text"])
        self.assertEqual(wia["url"], "https://www.kmwu.kr/bbs/board.php?bo_table=ce_B12&wr_id=220888")
        self.assertIn("이름은 본문에만", ev["un:ce_B12:220885"]["text"])
        self.assertNotIn("un:ce_B12:220886", ev)   # 포스코퓨처엠만 — 출입처 아님
        self.assertEqual(len([p for p in doc2["posts"]]), 4)

    def test_failures(self):
        lists = {"ce_B12": kmwu_list(["220884"]), "bodo": kctfu_list("bodo", ["468"]), "news": kctfu_list("news", ["972"])}
        doc = w.run(NOW, None, get=fake(lists)[0], sleep=lambda s: None)
        lists2 = dict(lists, ce_B12=kmwu_list(["220888", "220884"]))
        doc2 = w.run(NOW, doc, get=fake(lists2, fail=(("ce_B12", "220888"), "news"))[0], sleep=lambda s: None)
        by = {c["source"]: c for c in doc2["checks"]}
        self.assertEqual((by["금속노조 보도자료/성명"]["status"], by["화섬식품노조 주요소식"]["status"], doc2["status"]), ("partial", "failed", "partial"))
        self.assertNotIn("220888", doc2["seen"]["https://www.kmwu.kr|ce_B12"])   # 다음 실행에 다시
        allfail = w.run(NOW, doc, get=fake(lists, fail=("ce_B12", "bodo", "news"))[0], sleep=lambda s: None)
        self.assertEqual(allfail["status"], "failed")


if __name__ == "__main__":
    unittest.main()
