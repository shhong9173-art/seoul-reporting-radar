"""Aside 수집 코드(scripts/aside/kr_browser_collect.js)가 감시·Worker와 같은 목록을 쓰는지: 출입처 이름 정규식, 시·군, 노동위, TRN 주소."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import kr_local_notice_watch as w  # noqa: E402

JS = (ROOT / "scripts" / "aside" / "kr_browser_collect.js").read_text(encoding="utf-8")
WORKER = (ROOT / "cloudflare" / "local_browser.mjs").read_text(encoding="utf-8")
PARTS = re.split(r"^// ===== 토막 \d: .*=====$", JS, flags=re.M)


def worker_block(name):
    return re.search(r"const " + name + r" = \{(.*?)\};", WORKER, re.S).group(1)


class AsideCollect(unittest.TestCase):
    def test_four_parts(self):
        self.assertEqual(len(PARTS), 6)  # 머리말 + 토막 5개
        for p in PARTS[1:]:
            self.assertTrue(p.strip().startswith("{") and p.strip().endswith("}"), "토막마다 블록 { } — REPL 맨 위 이름이 남기 때문")

    def test_beat_regex_matches_watch_companies(self):
        m = re.search(r"const BEAT = /(.+)/;", JS)
        self.assertEqual(m.group(1), "|".join(rx for _, rx in w.COMPANIES))

    def test_cities_match_watch_and_worker(self):
        part1 = re.findall(r"\['([^']+)', '(https://[^']+)'\]", PARTS[1])
        watch = {c[0]: c[1] for c in w.BROWSER_CITIES} | {c[0]: c[1] for c in w.CITIES if c[0] in w.BROWSER_BACKUP}
        self.assertEqual(dict(part1), watch)
        worker = dict(re.findall(r"'?([가-힣][가-힣 ]*)'?: '(https://[^']+)'", worker_block("BROWSER_CITIES")))
        self.assertEqual(dict(part1), worker)
        names = json.loads("[" + re.search(r"const CITY_NAMES = \[(.*?)\];", PARTS[5]).group(1).replace("'", '"') + "]")
        self.assertEqual(names, [n for n, _ in part1])

    def test_labor_and_trn_match_worker(self):
        cmit = dict(re.findall(r"'?([가-힣]+위원회)'?: '(\d\d)'", worker_block("LABOR_CMIT")))
        part3 = {n: cd for n, _, cd in re.findall(r"\['([가-힣]+위원회)', '([a-z]*)', '(\d\d)'\]", PARTS[4])}
        self.assertEqual(part3, cmit)
        self.assertIn(re.search(r"url: '([^']+)'", worker_block("BROWSER_PAGES")).group(1), PARTS[4])

    def test_detail_url_matches_watch(self):
        # 토막 2가 여는 상세 주소 = 감시가 저장하는 원문 주소(기자가 누르는 링크)
        self.assertIn("method=selectOfrNotAncmt&methodnm=selectOfrNotAncmtRegst&not_ancmt_mgt_no=", PARTS[3])
        self.assertIn(w.HOMEPAGE_BOARDS["https://www.cheongju.go.kr"][1].split("{")[0], PARTS[3])
        self.assertIn(f"{w.BODY_CHARS}", PARTS[3])

    def test_only_listed_sites(self):
        hosts = set(re.findall(r"https://([a-z0-9.-]+)", "".join(PARTS[1:])))
        allowed = {re.match(r"https://([^/]+)", u).group(1) for _, u in re.findall(r"\['([^']+)', '(https://[^']+)'\]", PARTS[1])}
        self.assertEqual(hosts - allowed, {"www.industry.gov.au", "www.nlrc.go.kr"})

    @unittest.skipUnless(shutil.which("node"), "node 없음")
    def test_parts_parse(self):
        with tempfile.TemporaryDirectory() as d:
            for i, p in enumerate(PARTS[1:], 1):
                f = Path(d) / f"p{i}.mjs"
                f.write_text(p, encoding="utf-8")  # 맨 위 await — 모듈로 문법만 본다
                r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
