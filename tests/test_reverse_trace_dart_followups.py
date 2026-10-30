import copy
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from reverse_trace_dart_followups import build_queue, official_dart_url

BEAT_AT="2026-10-19T00:28:06+09:00"
QUE_AT="2026-10-19T00:28:38+09:00"
TRACE_AT="2026-10-19T03:27:18+09:00"
ARTICLE="3a34f9a7bf55c6afb1fe96d5"
ORIGINAL_SPLIT_RECEIPT="20260930000478"


def inputs():
    beat={"status":"industry_beat_official_receipt_review","generatedAt":BEAT_AT}
    row={"source":"DART_FILING","company":"현대모비스",
         "headline":"현대모비스 · 정기·주요공시 · 주요사항보고서(회사분할결정)",
         "officialReceiptNo":"20260930000478",
         "officialDate":"2026-09-30","sourceSnapshotAt":BEAT_AT,
         "sourceUrl":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260930000478",
         "originalEvidenceStage":"official_receipt_only_original_not_checked",
         "priorMediaCoverageVerified":False,"exclusiveConfirmed":False,
         "approvedForPitch":False}
    queue={"status":"official_date_triage","generatedAt":QUE_AT,
           "beatWideDartSourceAt":BEAT_AT,
           "confirmedScoops":0,"backgroundReference":[row],
           "freshOfficialReview":[],"incompleteOrStaleFeeds":["unverified provider"]}
    art={"articleId":ARTICLE,
         "title":"[단독] “현대모비스 램프사업 분할·매각 막아달라”…가처분 신청",
         "companies":["현대모비스"],"publicTraceClass":"U",
         "published":"2026-10-12T11:11:00+09:00"}
    trace={"status":"automotive_industry_exclusive_reverse_trace_unverified_candidates",
           "generatedAt":TRACE_AT,"items":[art],
           "totalObservedExclusiveHeadlines":1,"confirmedScoops":0}
    return trace,queue,beat


class DARTTitleReview(unittest.TestCase):
    def test_exact_2026_mobis_public_filing_only_generates_research_link(self):
        trace,official,beat=inputs()
        res=build_queue(trace,official,beat)
        self.assertEqual(res["candidatePairCount"],1)
        self.assertEqual(res["distinctOfficialReceipts"],1)
        self.assertEqual(res["humanValidatedYPN"],0)
        self.assertFalse(res["sameFactEstablished"])
        self.assertFalse(res["sourceCompletenessVerified"])
        one=res["items"][0]
        self.assertEqual(one["articleId"],ARTICLE)
        self.assertEqual(one["eventType"],"company_split")
        self.assertEqual(one["calendarDaysBetweenDates"],12)
        self.assertEqual(one["officialReceiptNo"],"20260930000478")
        self.assertEqual(one["originalEvidenceStage"],
                         "official_receipt_only_original_not_checked")
        self.assertFalse(one["officialOriginalBodyVerifiedForMatchedFact"])
        self.assertFalse(one["identicalUnderlyingCorporateEventVerified"])
        self.assertFalse(one["publicSourceAvailableBeforePublisherVerified"])
        self.assertFalse(one["publicFactOverlapVerified"])
        self.assertFalse(one["automaticYPNDecision"])
        self.assertFalse(one["exclusiveConfirmed"])

    def test_company_name_not_enough_to_match_unrelated_dart_receipt(self):
        trace,official,beat=inputs()
        official["backgroundReference"][0]["headline"]=(
            "현대모비스 · 영업(잠정)실적(공정공시)")
        self.assertEqual(build_queue(trace,official,beat)["candidatePairCount"],0)

    def test_other_issuer_or_report_after_article_rejected(self):
        trace,official,beat=inputs()
        official["backgroundReference"][0]["company"]="현대제철"
        self.assertEqual(build_queue(trace,official,beat)["candidatePairCount"],0)
        trace,official,beat=inputs()
        trace["items"][0]["published"]="2026-09-29T10:00:00+09:00"
        self.assertEqual(build_queue(trace,official,beat)["candidatePairCount"],0)

    def test_filing_receipt_url_and_source_snapshot_must_be_exact(self):
        trace,official,beat=inputs()
        for bad in (
            {"sourceSnapshotAt":"2026-10-18T00:00:00+09:00"},
            {"sourceUrl":"https://dart.fss.or.kr.evil.invalid/dsaf001/main.do?rcpNo=20260930000478"},
            {"officialDate":"2026-10-01"},
            {"officialReceiptNo":"20260930000479"},
            {"priorMediaCoverageVerified":True},
            {"originalEvidenceStage":"original_not_verified"},
        ):
            altered=copy.deepcopy(official)
            altered["backgroundReference"][0].update(bad)
            self.assertEqual(build_queue(trace,altered,beat)["candidatePairCount"],0,str(bad))
        self.assertFalse(official_dart_url(
            "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260930000478&Y=true",
            "20260930000478"))

    def test_mixed_source_snapshot_fails_not_empty(self):
        trace,official,beat=inputs()
        official["beatWideDartSourceAt"]="2026-10-18T00:00:00+09:00"
        with self.assertRaisesRegex(ValueError,"official_dart_snapshot"):
            build_queue(trace,official,beat)
        trace,official,beat=inputs()
        beat["generatedAt"]="corrupted"
        with self.assertRaisesRegex(ValueError,"official_dart_snapshot"):
            build_queue(trace,official,beat)

    def test_human_reviewed_article_is_not_reclassified_by_keyword(self):
        trace,official,beat=inputs()
        trace["items"][0]["publicTraceClass"]="Y"
        self.assertEqual(build_queue(trace,official,beat)["candidatePairCount"],0)

    def test_event_label_requires_exact_type_specific_story_word(self):
        trace,official,beat=inputs()
        tests=[
            ("주식소각결정","현대모비스 주식 소각결정","share_cancellation"),
            ("주요사항보고서(영업정지)","현대모비스 사업 중단","business_cessation"),
            ("단일판매ㆍ공급계약체결","현대모비스 차량부품 수주","contract"),
        ]
        for label,headline,expected in tests:
            with self.subTest(expected=expected):
                doc=copy.deepcopy(official)
                story=copy.deepcopy(trace)
                doc["backgroundReference"][0]["headline"]=label
                doc["backgroundReference"][0]["originalEvidenceStage"]="official_table_filing_fields_checked"
                story["items"][0]["title"]="[단독] "+headline
                matches=build_queue(story,doc,beat)["items"]
                self.assertEqual(len(matches),1)
                self.assertEqual(matches[0]["eventType"],expected)
                self.assertFalse(matches[0]["publicFactOverlapVerified"])

    def test_actual_main_digest_replay_not_assumed_permanent_exclusive(self):
        trace=json.loads((ROOT/"digests/reverse_trace_latest.json").read_text())
        official=json.loads((ROOT/"digests/official_event_triage_latest.json").read_text())
        beat=json.loads((ROOT/"digests/dart_beat_monitor_latest.json").read_text())
        out=build_queue(trace,official,beat)
        self.assertEqual(out["reverseTraceSourceAt"],trace["generatedAt"])
        self.assertEqual(out["dartOfficialSourceAt"],beat["generatedAt"])
        self.assertEqual(out["confirmedScoops"],0)
        for row in out["items"]:
            self.assertFalse(row["publicFactOverlapVerified"])
            self.assertFalse(row["exclusiveConfirmed"])
            self.assertFalse(row["automaticYPNDecision"])
            self.assertEqual(row["officialReceiptNo"][:8],
                             row["officialFilingDay"].replace("-",""))
            self.assertGreaterEqual(row["calendarDaysBetweenDates"],0)  # filing never after the article
        # The known example replays only while BOTH ends are still in their windows: the article in the
        # reverse-trace index and its original filing (2026-09-30 회사분할결정) in the DART beat window.
        # 10-30 the beat window rolled to start 10-01; only the 10-28 [기재정정] (filed after the
        # 10-12 article) remained, so no pair is correct — that is data ageing, not a matching failure.
        rows=official["backgroundReference"]+official["freshOfficialReview"]
        if (any(a["articleId"]==ARTICLE for a in trace["items"])
                and any(r.get("officialReceiptNo")==ORIGINAL_SPLIT_RECEIPT for r in rows)):
            self.assertTrue(any(a["articleId"]==ARTICLE for a in out["items"]))
        self.assertFalse(any(a["articleId"]==ARTICLE and a["officialFilingDay"]>"2026-10-12" for a in out["items"]))


if __name__=="__main__":
    unittest.main()
