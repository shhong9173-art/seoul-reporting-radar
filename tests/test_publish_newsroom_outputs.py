"""Exercise real bare-Git remotes, dirty collector and concurrent main writers."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from publish_newsroom_outputs import OUTPUTS, publish, selected


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
        self.assertEqual(publish(self.root,"news",before_push=race),"published")
        self.assertEqual(calls,[0,1])
        git(self.peer,"fetch","origin","main")
        self.assertEqual(self.remote_file("unrelated.txt"),"other main writer")
        self.assertEqual(json.loads(self.remote_file("data.json"))[0]["title"],
                         "fresh news 0")
        # No rebase/change to source checkout, even on rejected first push.
        self.assertEqual(git(self.root,"status","--porcelain").splitlines()[0][:2]," M")

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

    def test_inconsistent_generated_news_rejected_without_touching_remote(self):
        write_news(self.root,"wrong")
        (self.root/"data.js").write_text("window.ITEMS = [];\n")
        with self.assertRaises(ValueError):
            publish(self.root,"news")
        self.assertEqual(json.loads(self.remote_file("data.json"))[0]["title"],
                         "old news 0")


if __name__=="__main__":
    unittest.main()
