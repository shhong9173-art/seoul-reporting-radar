"""Parallel RSS fan-out stays bounded, stable and fail-closed per source."""
import sys
import threading
import time
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from rss_concurrent import collect_feeds


class ParallelFeedTests(unittest.TestCase):
    def test_results_order_is_definition_order_and_categories_preserved(self):
        seen=[]
        def parser(cat,query,*,global_feed=False,source_hint=""):
            if query=="second":time.sleep(0.04)
            if query=="first":time.sleep(0.10)
            return [{"q":query,"kind":cat,"global":global_feed,"hint":source_hint}]
        a,b=collect_feeds([("완성차","first"),("부품","second")],
             [("Reuters","third"),("Bloomberg","fourth")],parser,
             on_error=lambda *args:seen.append(args),workers=3)
        self.assertEqual([x["q"] for x in a],["first","second"])
        self.assertEqual([x["q"] for x in b],["third","fourth"])
        self.assertTrue(all(x["kind"]=="글로벌" for x in b))
        self.assertEqual([x["hint"] for x in b],["Reuters","Bloomberg"])
        self.assertTrue(all(x["global"] for x in b))
        self.assertEqual(seen,[])

    def test_unexpected_parse_error_is_reported_without_credentials(self):
        events=[]
        def parser(cat,query,*,global_feed=False,source_hint=""):
            if query=="bad":raise RuntimeError("SECRET_PLEASE_DO_NOT_LOG")
            return [{"q":query}]
        a,b=collect_feeds([("완성차","good"),("부품","bad")],[],
            parser,on_error=lambda c,g,t:events.append((c,g,t)),workers=2)
        self.assertEqual(a,[{"q":"good"}])
        self.assertEqual(b,[])
        self.assertEqual(events,[("부품",False,"RuntimeError")])
        self.assertNotIn("SECRET",str(events))

    def test_worker_limit_is_four(self):
        active=0; maximum=0;lock=threading.Lock()
        def parser(cat,query,*,global_feed=False,source_hint=""):
            nonlocal active,maximum
            with lock:
                active+=1;maximum=max(maximum,active)
            time.sleep(0.02)
            with lock:active-=1
            return [{"q":query}]
        domestic=[("완성차",str(i)) for i in range(12)]
        a,_=collect_feeds(domestic,[],parser,on_error=lambda *args:None,workers=3)
        self.assertEqual(len(a),12)
        self.assertLessEqual(maximum,3)
        self.assertGreater(maximum,1)

    def test_invalid_workers_and_empty_jobs_rejected(self):
        with self.assertRaises(ValueError):
            collect_feeds([],[],lambda *args:[],on_error=lambda *args:None)
        with self.assertRaises(ValueError):
            collect_feeds([("완성차","test")],[],lambda *args:[],
                on_error=lambda *args:None,workers=19)


if __name__=="__main__":
    unittest.main()
