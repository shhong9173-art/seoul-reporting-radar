"""An unpopular, widely reported or low-score article MUST be kept for scoops."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.press_coverage_index import (
    STATUS, hot_from_month, load_full_index, merge_index, update_from_news)
from scripts.press_coverage_gate import load_index as gate_load_index

KST=timezone(timedelta(hours=9))
NOW=datetime(2026,10,18,22,0,tzinfo=KST)


def article(title="현대차 이미 보도된 신차", *,
            at="2026-10-18T09:00:00+09:00",
            source="경제신문", score=12,
            url="https://example.com/article/1",
            global_feed=False):
    return {
        "title":title,"published":at,"sourceName":source,
        "url":url, "global":global_feed,"companies":["현대차"],
        "summary":"기보도 현대차 계획 관련 100억원",
        "pitchScore":score,"clusterCount":18,"exclusive":False
    }


class UnfilteredPriorCoverage(unittest.TestCase):
    def test_widely_reported_low_score_is_retained(self):
        press=[
            article(),
            article("현대차 기보도 반복",url="https://example.com/article/2",score=0),
            article("국내 단독 보도",url="https://example.com/article/3",score=25),
            article("Overseas item",url="https://example.com/article/4",
                    global_feed=True)]
        result=merge_index(None,press,now=NOW)
        self.assertEqual(result["itemCount"],3)
        self.assertEqual(result["newlyIndexedArticleCount"],3)
        self.assertFalse(result["proofOfNoPriorCoverage"])
        self.assertTrue(result["firstRunBaseline"])
        self.assertEqual(result["retentionDays"],365)
        self.assertNotIn("pitchScore",result["items"][0])
        self.assertTrue(all(x["fulltextReviewed"] is False for x in result["items"]))

    def test_new_score_change_does_not_erase_same_article(self):
        first=merge_index(None,[article()],now=NOW)
        second=merge_index(first,[article(score=95)],now=NOW)
        self.assertEqual(second["itemCount"],1)
        self.assertEqual(second["newlyIndexedArticleCount"],0)
        self.assertFalse(second["firstRunBaseline"])

    def test_stores_365_days_not_only_90(self):
        old=(NOW-timedelta(days=180)).isoformat()
        stale=(NOW-timedelta(days=367)).isoformat()
        today=article(at=old)
        result=merge_index(None,[today],now=NOW)
        self.assertEqual(result["itemCount"],1)
        rerun=merge_index(result,[article("stale",at=stale,url="https://example.com/old")],
                          now=NOW+timedelta(days=1))
        self.assertEqual(rerun["itemCount"],1)

    def test_undated_and_bad_published_must_not_become_now(self):
        bad=article(at="unknown")
        missing=article(at="")
        out=merge_index(None,[bad,missing,article()],now=NOW)
        self.assertEqual(out["malformedOrUndatedInputCount"],2)
        self.assertEqual(out["itemCount"],1)

    def test_corrupt_history_is_not_silently_zeroed(self):
        with self.assertRaises(ValueError):
            merge_index({"status":"bad","items":[article()]},[],now=NOW)
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"index.json"
            target.write_text('{"status": "unexpected"}',encoding="utf-8")
            before=target.read_text()
            with self.assertRaises(ValueError):
                update_from_news([article()],path=target,now=NOW)
            self.assertEqual(target.read_text(),before)

    def test_persisted_compact_index_is_reloaded_and_unique(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"coverage.json"
            first=update_from_news([article()],path=target,now=NOW)
            second=update_from_news([article()],path=target,now=NOW)
            read=json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(first["itemCount"],second["itemCount"])
            self.assertEqual(read["status"],STATUS)
            self.assertEqual(read["itemCount"],1)
            self.assertIn("numbers",read["items"][0])
            self.assertNotIn("summary",read["items"][0])
            self.assertIn("sourceName",read["items"][0])
            self.assertEqual(read["items"][0]["companies"],["현대차"])

    def test_numbers_from_summary_survive_the_next_merge(self):
        # 11-24: 저장된 줄을 다시 합칠 때 요약 속 숫자(100억원)가 사라졌다
        first=merge_index(None,[article()],now=NOW)
        self.assertEqual(first["items"][0]["numbers"],["100억"])
        second=merge_index(first,[],now=NOW)
        self.assertEqual(second["items"][0]["numbers"],["100억"])

    def test_empty_feed_not_negative_proof(self):
        out=merge_index(None,[],now=NOW)
        self.assertEqual(out["itemCount"],0)
        self.assertFalse(out["proofOfNoPriorCoverage"])
        self.assertTrue(out["firstRunBaseline"])


class MonthShards(unittest.TestCase):
    """11-24: 1년 색인 한 파일이 12MiB 발행 상한을 넘어 Auto Desk가 19회 연속 실패 — 이번 달·지난달만 latest, 그 전은 달 파일."""

    DEC=datetime(2026,12,2,9,0,tzinfo=KST)

    def rows(self):
        return [article("10월 기사",at="2026-10-20T09:00:00+09:00",url="https://example.com/10"),
                # UTC로 10-31 16:00 = 한국 11-01 01:00 — 한국 날짜로 11월
                article("UTC 경계",at="2026-10-31T16:00:00+00:00",url="https://example.com/b"),
                article("11월 기사",at="2026-11-24T09:00:00+09:00",url="https://example.com/11"),
                article("12월 기사",at="2026-12-01T09:00:00+09:00",url="https://example.com/12")]

    def test_hot_window_is_this_and_previous_month(self):
        self.assertEqual(hot_from_month(self.DEC),"2026-11")
        self.assertEqual(hot_from_month(datetime(2027,1,1,0,30,tzinfo=KST)),"2026-12")
        # UTC로는 12-31이어도 한국 시각 1월이면 1월 기준
        self.assertEqual(hot_from_month(datetime(2026,12,31,16,0,tzinfo=timezone.utc)),"2026-12")

    def test_split_writes_closed_months_and_reloads_whole_year(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"digests/press_coverage_index_latest.json"
            result=update_from_news(self.rows(),path=target,now=self.DEC)
            self.assertEqual(result["itemCount"],4)               # 돌려주는 값은 전체
            hot=json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(hot["status"],STATUS)
            self.assertEqual(hot["itemCount"],len(hot["items"]))  # 기존 검사(itemCount==len(items))는 latest에서 그대로
            self.assertEqual(hot["itemCount"],3)
            self.assertEqual(hot["totalItemCount"],4)
            self.assertEqual(hot["hotFromMonth"],"2026-11")
            self.assertEqual(hot["retentionDays"],365)
            self.assertEqual([(x["month"],x["file"],x["itemCount"]) for x in hot["coldShards"]],
                             [("2026-10","press_coverage_index/2026-10.json",1)])
            shard=json.loads((Path(tmp)/"digests/press_coverage_index/2026-10.json").read_text(encoding="utf-8"))
            self.assertEqual(shard["month"],"2026-10")
            self.assertNotIn("generatedAt",shard)                 # 같은 내용이면 같은 바이트
            self.assertEqual([x["title"] for x in shard["items"]],["10월 기사"])
            full=load_full_index(target)
            self.assertEqual(full["itemCount"],4)
            self.assertEqual(full["hotItemCount"],3)
            self.assertEqual([x["title"] for x in full["items"]],["12월 기사","11월 기사","UTC 경계","10월 기사"])
            gate=gate_load_index(target)
            self.assertEqual(gate["itemCount"],4)
            self.assertEqual(len(gate["items"]),4)
            # 다음 실행: 지난 달 파일은 바이트가 같아 다시 쓰지 않는다
            path=Path(tmp)/"digests/press_coverage_index/2026-10.json"
            before=path.read_bytes()
            stamp=1_700_000_000_000_000_000
            import os
            os.utime(path,ns=(stamp,stamp))
            again=update_from_news([article("12월 둘째",at="2026-12-02T08:00:00+09:00",url="https://example.com/12b")],
                                   path=target,now=self.DEC)
            self.assertEqual(again["itemCount"],5)
            self.assertEqual(again["newlyIndexedArticleCount"],1)
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(path.stat().st_mtime_ns,stamp)
            # 늦게 들어온 10월 기사는 10월 파일로 — 목록의 sha256·건수도 바뀐다
            late=update_from_news([article("늦은 10월",at="2026-10-05T09:00:00+09:00",url="https://example.com/late")],
                                  path=target,now=self.DEC)
            hot=json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(late["itemCount"],6)
            self.assertEqual(hot["coldShards"][0]["itemCount"],2)
            self.assertNotEqual(path.read_bytes(),before)
            self.assertEqual(load_full_index(target)["itemCount"],6)

    def test_month_files_roll_over_on_the_first_of_the_month(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"digests/press_coverage_index_latest.json"
            update_from_news(self.rows(),path=target,now=datetime(2026,11,30,23,0,tzinfo=KST))
            hot=json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(hot["coldShards"],[])                # 11월 말: 10·11월 모두 latest
            self.assertEqual(hot["itemCount"],3)                  # 12월 기사는 '지금+1시간' 뒤라 아직 안 받음
            update_from_news([],path=target,now=self.DEC)
            hot=json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual([x["month"] for x in hot["coldShards"]],["2026-10"])
            self.assertEqual(load_full_index(target)["itemCount"],3)

    def test_old_single_file_converts_without_losing_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"digests/press_coverage_index_latest.json"
            target.parent.mkdir(parents=True)
            old=merge_index(None,self.rows()[:3],now=datetime(2026,11,24,10,0,tzinfo=KST))
            target.write_text(json.dumps(old,ensure_ascii=False),encoding="utf-8")   # 11-24까지의 한 파일 형식
            self.assertEqual(load_full_index(target)["itemCount"],3)
            self.assertEqual(gate_load_index(target)["itemCount"],3)
            out=update_from_news([],path=target,now=self.DEC)
            self.assertEqual(out["itemCount"],3)
            self.assertEqual(out["priorRetainedCount"],3)
            self.assertEqual(load_full_index(target)["itemCount"],3)

    def test_missing_or_tampered_month_file_stops_instead_of_erasing(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"digests/press_coverage_index_latest.json"
            update_from_news(self.rows(),path=target,now=self.DEC)
            shard=Path(tmp)/"digests/press_coverage_index/2026-10.json"
            latest=target.read_text(encoding="utf-8")
            shard.write_text(shard.read_text(encoding="utf-8").replace("10월 기사","바뀐 제목"),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"press_index_shard_hash_mismatch"):
                load_full_index(target)
            with self.assertRaisesRegex(ValueError,"press_index_shard_hash_mismatch"):
                update_from_news([article("새 기사",at="2026-12-02T08:00:00+09:00",url="https://example.com/n")],
                                 path=target,now=self.DEC)
            self.assertEqual(target.read_text(encoding="utf-8"),latest)   # latest를 덮지 않음
            self.assertEqual(gate_load_index(target)["status"],"missing_or_invalid_index")
            shard.unlink()
            with self.assertRaisesRegex(ValueError,"press_index_shard_missing"):
                load_full_index(target)
            self.assertEqual(gate_load_index(target)["status"],"missing_or_invalid_index")

    def test_forged_manifest_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"digests/press_coverage_index_latest.json"
            update_from_news(self.rows(),path=target,now=self.DEC)
            hot=json.loads(target.read_text(encoding="utf-8"))
            for bad in ("../secrets.json","press_coverage_index/2026-13.json","press_coverage_index/2026-09.json"):
                forged=dict(hot,coldShards=[dict(hot["coldShards"][0],file=bad)])
                target.write_text(json.dumps(forged,ensure_ascii=False),encoding="utf-8")
                with self.assertRaisesRegex(ValueError,"press_index_shard_manifest_invalid"):
                    load_full_index(target)
            forged=dict(hot,totalItemCount=99)
            target.write_text(json.dumps(forged,ensure_ascii=False),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"press_index_shard_total_mismatch"):
                load_full_index(target)

    def test_year_old_months_leave_the_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"digests/press_coverage_index_latest.json"
            update_from_news(self.rows(),path=target,now=self.DEC)
            later=datetime(2027,10,25,9,0,tzinfo=KST)                # 2026-10-20 기사는 365일 지남
            out=update_from_news([],path=target,now=later)
            hot=json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual([x["month"] for x in hot["coldShards"]],["2026-12","2026-11"])
            self.assertEqual(out["itemCount"],3)
            self.assertEqual(load_full_index(target)["itemCount"],3)


if __name__=="__main__":
    unittest.main()
