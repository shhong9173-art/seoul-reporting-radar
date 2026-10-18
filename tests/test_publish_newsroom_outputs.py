"""Exercise real bare-Git remotes, dirty collector and concurrent main writers."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from publish_newsroom_outputs import OUTPUTS, publish, selected, output_size_limit


def git(cwd,*args):
    p=subprocess.run(["git",*args],cwd=cwd,capture_output=True,text=True)
    if p.returncode:
        raise RuntimeError("git_failed "+args[0])
    return p.stdout.strip()


def make_data(label):
    articles=[{"title":label+" news "+str(i),"url":"https://news.example/"+str(i)}
              for i in range(12)]
    return articles


def write_news(root,label):
    articles=make_data(label)
    (root/"data.json").write_text(json.dumps(articles),encoding="utf-8")
    (root/"data.js").write_text("window.ITEMS = "+json.dumps(articles)+";\n",encoding="utf-8")
    for name in OUTPUTS["news"]:
        p=root/name
        if p.exists() or name in ("data.js","data.json"):
            continue
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text("[]\n" if name in ("global.json","archive.json","pitch.json") else "{}\n")


def write_scoop(root,title):
    for p in OUTPUTS["scoop"]:
        (root/p).write_text(json.dumps({"items":[{"title":title}]}),encoding="utf-8")


class PublisherIntegration(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        top=Path(self.t.name)
        self.remote=top/"remote.git"
        git(top,"init","--bare","--initial-branch=main",str(self.remote))
        self.root=top/"news"
        git(top,"clone",str(self.remote),str(self.root))
        git(self.root,"config","user.name","Test")
        git(self.root,"config","user.email","test@example.com")
        write_news(self.root,"old")
        write_scoop(self.root,"existing scoop")
        (self.root/"pitch_builder.py").write_text("base version\n")
        (self.root/"unrelated.txt").write_text("base\n")
        git(self.root,"add",".")
        git(self.root,"commit","-m","baseline")
        git(self.root,"push","-u","origin","main")
        self.peer=top/"peer"
        git(top,"clone",str(self.remote),str(self.peer))
        git(self.peer,"config","user.name","Other writer")
        git(self.peer,"config","user.email","other@example.com")

    def tearDown(self):
        self.t.cleanup()

    def remote_file(self,path):
        return git(self.peer,"show","origin/main:"+path)

    def test_news_never_overwrites_scoop_and_leaves_dirty_collector_untouched(self):
        # Independent scoop writer gets a newer result just before newsroom publish.
        write_scoop(self.peer,"other independent scoop")
        git(self.peer,"add",*OUTPUTS["scoop"])
        git(self.peer,"commit","-m","new scoop results")
        git(self.peer,"push","origin","main")
        write_news(self.root,"updated")
        write_scoop(self.root,"stale local scoop")
        (self.root/"pitch_builder.py").write_text("dirty generated source edit\n")
        self.assertEqual(publish(self.root,"news"),"published")
        git(self.peer,"fetch","origin","main")
        self.assertEqual(json.loads(self.remote_file("scoop.json"))["items"][0]["title"],
                         "other independent scoop")
        self.assertEqual(json.loads(self.remote_file("data.json"))[0]["title"],
                         "updated news 0")
        self.assertEqual(self.remote_file("pitch_builder.py"),"base version")
        self.assertEqual((self.root/"pitch_builder.py").read_text(),"dirty generated source edit\n")
        self.assertEqual(json.loads((self.root/"scoop.json").read_text())["items"][0]["title"],
                         "stale local scoop")

    def test_real_non_fast_forward_retry_rebuilds_without_rebase(self):
        write_news(self.root,"fresh")
        calls=[]
        def race(attempt):
            calls.append(attempt)
            if attempt==0:
                (self.peer/"unrelated.txt").write_text("other main writer\n")
                git(self.peer,"add","unrelated.txt")
                git(self.peer,"commit","-m","concurrent independent change")
                git(self.peer,"push","origin","main")
        source_head=git(self.root,"rev-parse","HEAD")
        self.assertEqual(publish(self.root,"news",before_push=race),"published")
        self.assertEqual(calls,[0,1])
        git(self.peer,"fetch","origin","main")
        self.assertEqual(self.remote_file("unrelated.txt"),"other main writer")
        self.assertEqual(json.loads(self.remote_file("data.json"))[0]["title"],
                         "fresh news 0")
        # No rebase/change to source checkout, even on rejected first push.
        self.assertEqual(git(self.root,"rev-parse","HEAD"),source_head)
        self.assertEqual(json.loads((self.root/"data.json").read_text())[0]["title"],
                         "fresh news 0")
        self.assertTrue(git(self.root,"status","--porcelain"))

    def test_news_publish_recovers_after_four_consecutive_other_main_writers(self):
        # Regression for the 2026-10-18 real newsroom publishing failure:
        # a validated 389-row coverage index was built, but four fast
        # non-fast-forward push races prevented any output from reaching main.
        write_news(self.root,"latest validated")
        races=[]
        delays=[]
        def race(attempt):
            if attempt < 4:
                git(self.peer,"fetch","origin","main")
                git(self.peer,"reset","--hard","origin/main")
                (self.peer/"unrelated.txt").write_text(
                    "another live producer update "+str(attempt)+"\n")
                git(self.peer,"add","unrelated.txt")
                git(self.peer,"commit","-m","independent producer "+str(attempt))
                git(self.peer,"push","origin","main")
                races.append(attempt)
        result=publish(self.root,"news",attempts=6,
                       before_push=race,retry_sleep=delays.append)
        self.assertEqual(result,"published")
        self.assertEqual(races,[0,1,2,3])
        self.assertEqual(delays,[1,2,4,8])
        git(self.peer,"fetch","origin","main")
        self.assertEqual(
            json.loads(self.remote_file("data.json"))[0]["title"],
            "latest validated news 0")
        self.assertEqual(self.remote_file("unrelated.txt"),
                         "another live producer update 3")
        self.assertIn("digests/press_coverage_index_latest.json",
                      OUTPUTS["news"])

    def test_concurrent_official_registry_survives_stale_news_refresh(self):
        self.assertNotIn("dart_corp_codes.json",OUTPUTS["news"])
        official={"companies":{"현대자동차":{"corp_code":"00164742","stock_code":"005380"},
            "KG스틸":{"corp_code":"00115676","stock_code":"016380"}}}
        # News checkout predates the issuer verification; official registry
        # writer commits the newly validated KG Steel id to remote main.
        (self.root/"dart_corp_codes.json").write_text(
            json.dumps({"companies":{"현대자동차":{"corp_code":"00164742"}}}))
        (self.peer/"dart_corp_codes.json").write_text(json.dumps(official))
        git(self.peer,"add","dart_corp_codes.json")
        git(self.peer,"commit","-m","Official stock plus legal issuer registry")
        git(self.peer,"push","origin","main")
        write_news(self.root,"headline updated")
        self.assertEqual(publish(self.root,"news"),"published")
        git(self.peer,"fetch","origin","main")
        self.assertEqual(json.loads(self.remote_file("dart_corp_codes.json")),official)
        self.assertEqual(json.loads(self.remote_file("data.json"))[0]["title"],
                         "headline updated news 0")

    def test_dart_beat_official_atomic_writer_fails_closed_on_missing_issuer(self):
        from datetime import datetime,timezone,timedelta
        ts=datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")
        codes={"companies":{"KG스틸":{"corp_code":"00115676","stock_code":"016380"}}}
        coverage={"generatedAt":ts,"status":"official_corp_code_registry_checked",
                  "scope":1,"knownWithCode":1,
                  "companies":[{"company":"KG스틸","corpCode":"00115676",
                      "status":"resolved_unique_official_stock_and_legal_name",
                      "officialListedStockCodeProof":"016380"}]}
        monitor={"generatedAt":ts,
                 "status":"industry_beat_official_receipt_review",
                 "scopeCompanyCount":1,"companiesCodeVerified":1,
                 "companiesUnresolved":0,"companiesWithSourceErrors":0,
                 "confirmedScoops":0,"approvedArticles":0}
        changed={"sourceGeneratedAt":ts,
                 "status":"official_receipt_change_review_not_exclusive",
                 "confirmedScoops":0,"approvedArticles":0}
        docs=[codes,coverage,monitor,changed]
        for name,doc in zip(OUTPUTS["dart_beat"],docs):
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text(json.dumps(doc))
        self.assertEqual(publish(self.root,"dart_beat"),"published")
        git(self.peer,"fetch","origin","main")
        saved=json.loads(self.remote_file("dart_corp_codes.json"))
        self.assertEqual(saved["companies"]["KG스틸"]["corp_code"],"00115676")
        (self.root/"dart_corp_codes.json").write_text(json.dumps({"companies":{}}))
        with self.assertRaisesRegex(ValueError,"official_issuer_id_missing_in_published_registry"):
            selected(self.root,"dart_beat")
        (self.root/"dart_corp_codes.json").write_text(json.dumps(codes))
        coverage["companies"][0]["officialListedStockCodeProof"]="wrong"
        (self.root/OUTPUTS["dart_beat"][1]).write_text(json.dumps(coverage))
        with self.assertRaisesRegex(ValueError,"listed_issuer_stock_identity_unverified"):
            selected(self.root,"dart_beat")

    def test_health_publishes_despite_dirty_source_and_rejects_bad_schema(self):
        report={
          "status":"incomplete_queries_or_provider_errors",
          "newsDatasetApprovedForPublish":False,
          "zeroFetchedMeansZeroPublishedStories":False,
          "checks":[{"category":"부품","status":"transport_or_xml_error"}],
        }
        path=self.root/OUTPUTS["health"][0]
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(report,ensure_ascii=False))
        (self.root/"pitch_builder.py").write_text("locally dirty\n")
        self.assertEqual(publish(self.root,"health"),"published")
        git(self.peer,"fetch","origin","main")
        data=json.loads(self.remote_file(OUTPUTS["health"][0]))
        self.assertFalse(data["newsDatasetApprovedForPublish"])
        self.assertEqual(self.remote_file("pitch_builder.py"),"base version")
        self.assertEqual(publish(self.root,"health"),"no_changes")
        path.write_text(json.dumps({"newsDatasetApprovedForPublish":True}))
        with self.assertRaises(ValueError):
            selected(self.root,"health")

    def test_scoop_owner_isolated_and_fails_closed_with_missing_source(self):
        write_scoop(self.root,"scoop author")
        self.assertEqual(publish(self.root,"scoop"),"published")
        git(self.peer,"fetch","origin","main")
        self.assertEqual(json.loads(self.remote_file("scoop.json"))["items"][0]["title"],
                         "scoop author")
        self.assertEqual(json.loads(self.remote_file("data.json"))[0]["title"],
                         "old news 0")
        (self.root/"scoop.json").unlink()
        with self.assertRaises(ValueError):
            selected(self.root,"scoop")

    def test_actual_archive_size_is_allowed_but_oversized_other_files_fail(self):
        # Production 90-day archive (2026-10-17) is 16,203,874 bytes.
        self.assertGreaterEqual(output_size_limit("archive.json"),16_203_874)
        self.assertLess(output_size_limit("data.json"),16_203_874)
        self.assertLessEqual(output_size_limit("archive.json"),32*1024*1024)
        payload='["'+('x'*(12*1024*1024))+'"]'
        (self.root/"archive.json").write_text(payload,encoding="utf-8")
        self.assertIn("archive.json",selected(self.root,"news"))
        (self.root/"data.json").write_text(payload,encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"invalid_generated_output: data.json"):
            selected(self.root,"news")

    def test_reporting_queue_is_single_owner_and_never_publishes_scoops(self):
        self.assertEqual(OUTPUTS["queue"],
                         ("digests/reporting_evidence_queue_latest.json",))
        source=self.root/OUTPUTS["queue"][0]
        source.parent.mkdir(parents=True,exist_ok=True)
        item={"exclusiveConfirmed":False,"approvedForPitch":False,
              "pressFulltextReviewed":False,"company":"대한전선"}
        good={"status":"reporter_evidence_queue_not_exclusive",
              "confirmedScoops":0,"approvedArticles":0,"totalRows":1,
              "items":[item]}
        source.write_text(json.dumps(good,ensure_ascii=False))
        self.assertEqual(publish(self.root,"queue"),"published")
        git(self.peer,"fetch","origin","main")
        stored=json.loads(self.remote_file(OUTPUTS["queue"][0]))
        self.assertEqual(stored["items"][0]["company"],"대한전선")
        self.assertEqual(self.remote_file("scoop.json"),
                         (self.root/"scoop.json").read_text().strip())
        bad={**good,"items":[{**item,"exclusiveConfirmed":True}]}
        source.write_text(json.dumps(bad))
        with self.assertRaisesRegex(ValueError,"invalid_reporting_queue_evidence"):
            selected(self.root,"queue")

    def test_newer_official_dart_queue_cannot_be_rolled_back_by_old_run(self):
        # A queued newspaper UI build can finish after a newer official
        # DART monitor publish; only source-scan recency should decide.
        filename=OUTPUTS["queue"][0]
        local=self.root/filename
        remote=self.peer/filename
        local.parent.mkdir(parents=True,exist_ok=True)
        remote.parent.mkdir(parents=True,exist_ok=True)
        item={"exclusiveConfirmed":False,"approvedForPitch":False,
              "pressFulltextReviewed":False,"company":"KG스틸"}
        def queue(at,title):
            return {"status":"reporter_evidence_queue_not_exclusive",
                    "confirmedScoops":0,"approvedArticles":0,
                    "totalRows":1,"items":[{**item,"title":title}],
                    "sourceHealth":{"dartBeat":{
                        "status":"source_partial_coverage","generatedAt":at}}}
        older=queue("2026-10-17T18:00:00+09:00","old stale snapshot")
        newer=queue("2026-10-17T20:45:00+09:00","value-up official title")
        local.write_text(json.dumps(older))
        remote.write_text(json.dumps(newer))
        git(self.peer,"add",filename)
        git(self.peer,"commit","-m","newer official DART source")
        git(self.peer,"push","origin","main")
        self.assertEqual(publish(self.root,"queue"),"skipped_stale_dart_source")
        git(self.peer,"fetch","origin","main")
        self.assertEqual(json.loads(self.remote_file(filename))["items"][0]["title"],
                         "value-up official title")
        # A later scanner legitimately supersedes the earlier version.
        fresh=queue("2026-10-17T21:00:00+09:00","newer verified source")
        local.write_text(json.dumps(fresh))
        self.assertEqual(publish(self.root,"queue"),"published")
        git(self.peer,"fetch","origin","main")
        self.assertEqual(json.loads(self.remote_file(filename))["items"][0]["title"],
                         "newer verified source")
        # Missing source must not displace already confirmed DART coverage.
        missing={**older,"sourceHealth":{"dartBeat":{
            "status":"unavailable_or_schema_mismatch",
            "generatedAt":"2026-10-17T22:00:00+09:00"}}}
        local.write_text(json.dumps(missing))
        self.assertEqual(publish(self.root,"queue"),"skipped_stale_dart_source")
        git(self.peer,"fetch","origin","main")
        self.assertEqual(json.loads(self.remote_file(filename))["items"][0]["title"],
                         "newer verified source")

    def test_real_crossborder_official_snapshot_owned_atomically(self):
        # CI replays all official snapshots without querying Slovak API/PDF.
        real=Path(__file__).resolve().parents[1]
        for name in OUTPUTS["crossborder"]:
            source=real/name
            self.assertTrue(source.is_file(),name)
            target=self.root/name
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(source.read_bytes())
        self.assertIn("digests/crossborder_source_gap_latest.json",
                      selected(self.root,"crossborder"))
        self.assertEqual(publish(self.root,"crossborder"),"published")
        git(self.peer,"fetch","origin","main")
        published=json.loads(self.remote_file(
            "digests/crossborder_source_gap_latest.json"))
        self.assertEqual(published["confirmedScoops"],0)
        self.assertFalse(published["foreignParentCashTransferVerified"])
        self.assertEqual(self.remote_file("scoop.json"),
                         (self.root/"scoop.json").read_text().strip())
        path=self.root/"digests/crossborder_source_gap_latest.json"
        forged={**published,"foreignParentCashTransferVerified":True}
        path.write_text(json.dumps(forged))
        with self.assertRaisesRegex(ValueError,"invalid_crossborder_source_evidence"):
            selected(self.root,"crossborder")

    def test_inconsistent_generated_news_rejected_without_touching_remote(self):
        write_news(self.root,"wrong")
        (self.root/"data.js").write_text("window.ITEMS = [];\n")
        with self.assertRaises(ValueError):
            publish(self.root,"news")
        self.assertEqual(json.loads(self.remote_file("data.json"))[0]["title"],
                         "old news 0")


if __name__=="__main__":
    unittest.main()
