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
sys.path.insert(0, str(ROOT / "tests"))
import kr_local_notice_watch as w  # noqa: E402

JS = (ROOT / "scripts" / "aside" / "kr_browser_collect.js").read_text(encoding="utf-8")
WORKER = (ROOT / "cloudflare" / "local_browser.mjs").read_text(encoding="utf-8")
PARTS = re.split(r"^// ===== 토막 \d: .*=====$", JS, flags=re.M)


def worker_block(name):
    return re.search(r"const " + name + r" = \{(.*?)\};", WORKER, re.S).group(1)


class AsideCollect(unittest.TestCase):
    def test_four_parts(self):
        self.assertEqual(len(PARTS), 7)  # 머리말 + 토막 6개
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
        names = json.loads("[" + re.search(r"const CITY_NAMES = \[(.*?)\];", PARTS[6]).group(1).replace("'", '"') + "]")
        self.assertEqual(names, [n for n, _ in part1])
        # radar_today 수집 상태가 '이 길뿐인 시·군'으로 보는 목록 = 감시의 BROWSER_CITIES(대신 쓰는 곳 BROWSER_BACKUP은 뺌)
        only = json.loads("[" + re.search(r"export const BROWSER_ONLY = \[(.*?)\];", WORKER).group(1).replace("'", '"') + "]")
        self.assertEqual(only, [c[0] for c in w.BROWSER_CITIES])
        self.assertFalse(set(only) & w.BROWSER_BACKUP)

    def test_labor_and_trn_match_worker(self):
        cmit = dict(re.findall(r"'?([가-힣]+위원회)'?: '(\d\d)'", worker_block("LABOR_CMIT")))
        part3 = {n: cd for n, _, cd in re.findall(r"\['([가-힣]+위원회)', '([a-z]*)', '(\d\d)'\]", PARTS[5])}
        self.assertEqual(part3, cmit)
        urls = re.findall(r"url: '([^']+)'", worker_block("BROWSER_PAGES"))
        self.assertEqual(len(urls), 2)   # 호주 TRN 목록 + 진행 사건 목록(EPR)
        for u in urls:
            self.assertIn(u, PARTS[5])

    def test_epr_rows(self):
        # 토막 5의 사건 공개기록 줄: 첫 칸이 종류, 둘째 칸이 사건 번호 — au_epr_cases.py가 같은 낱말로 읽는다
        sys.path.insert(0, str(ROOT / "scripts"))
        import au_epr_cases
        for kind in au_epr_cases.KINDS:
            self.assertIn(f"['{kind}', ", PARTS[5])
        # 사건 페이지 주소는 목록 주소 + 사건 번호(영문·숫자)로만 만든다 — 목록에 적힌 다른 주소를 열지 않는다
        self.assertIn("page(EPR + '/' + c.no", PARTS[5])
        self.assertIn("([A-Za-z0-9-]{1,20})", PARTS[5])
        # 대화로 옮겨 올리는 SUBMIT 줄에는 사건 공개기록을 넣지 않는다(양이 많음)
        self.assertEqual(PARTS[6].count("console.log('SUBMIT ' + JSON.stringify(small));"), 2)
        self.assertIn("const small = { ...payload, pages: pages.slice(0, 1) };", PARTS[6])
        self.assertNotIn("JSON.stringify(payload));\n    console", PARTS[6].replace("}, JSON.stringify(payload));", ""))

    def test_detail_url_matches_watch(self):
        # 토막 2가 여는 상세 주소 = 감시가 저장하는 원문 주소(기자가 누르는 링크)
        self.assertIn("method=selectOfrNotAncmt&methodnm=selectOfrNotAncmtRegst&not_ancmt_mgt_no=", PARTS[3])
        self.assertIn(w.HOMEPAGE_BOARDS["https://www.cheongju.go.kr"][1].split("{")[0], PARTS[3])
        self.assertIn(f"{w.BODY_CHARS}", PARTS[3])

    def test_only_listed_sites(self):
        hosts = set(re.findall(r"https://([a-z0-9.-]+)", "".join(PARTS[1:])))
        allowed = {re.match(r"https://([^/]+)", u).group(1) for _, u in re.findall(r"\['([^']+)', '(https://[^']+)'\]", PARTS[1])}
        self.assertEqual(hosts - allowed, {"www.industry.gov.au", "www.nlrc.go.kr", "seoul-reporting-radar.shhong9173.workers.dev"})

    def test_upload_never_prints_key(self):
        # 열쇠는 사이트 저장소에서 읽어 보내기만 한다 — console.log에 열쇠 변수가 들어가면 안 됨
        reg = (ROOT / "scripts" / "aside" / "register_upload_key.js").read_text(encoding="utf-8")
        for code in (PARTS[6], reg):
            for line in re.findall(r"console\.log\((.*)\);", code):
                self.assertNotRegex(line, r"\bk\b|localStorage|radarUploadKey")
        self.assertIn("radarUploadKey", PARTS[6])
        self.assertIn("'/upload/browser'", PARTS[6])  # 같은 사이트(창)에서만 보낸다

    def test_attachment_rules_match_watch(self):
        # 토막 4가 고르는 첨부·내려받기 주소·글자 한도 = 감시 read_attachments
        self.assertIn(w.FILEDOWN, PARTS[4])
        self.assertIn("/" + w.ATTACH_READ.pattern + "/i", PARTS[4])
        self.assertIn("/" + w.ATTACH_FIRST.pattern + "/", PARTS[4])
        self.assertIn(f".slice(0, {w.ATTACH_MAX})", PARTS[4])
        self.assertIn("text.slice(0, 4000)", PARTS[4])
        self.assertEqual(w.ATTACH_BYTES, 6_000_000)
        self.assertIn("6000000", PARTS[4])
        # 보내는 줄에는 첨부 링크·Referer를 넣지 않는다
        self.assertIn("({ mgt: x.mgt, cells: x.cells, ...(x.detail ? { detail: x.detail } : {}) })", PARTS[6])

    def test_no_unicode_escapes(self):
        # 예약 작업 지시문에 코드를 붙일 때 역슬래시-u 네 자리 이스케이프가 실제 글자로 바뀌어(11-07 저장본에서 사용자 영역 글자가 사라져
        # 정규식이 하이픈을 지우는 꼴이 됨) 코드에 쓰지 않는다
        self.assertIsNone(re.search(r"\\u[0-9a-fA-F]{4}|\\u\{", JS))
        reg = (ROOT / "scripts" / "aside" / "register_upload_key.js").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"\\u[0-9a-fA-F]{4}|\\u\{", reg))

    @unittest.skipUnless(shutil.which("node"), "node 없음")
    def test_hwp_text_matches_python(self):
        # 토막 4의 hwpText(기자 컴퓨터에서 hwp 풀기)가 감시 hwp_text와 같은 글자를 낸다 — 시험용 HWP(미니·일반 섹터, 압축·비압축)
        import hwp_fixture
        src = JS[JS.index("    const hwpText = async (b64) => {"):JS.index("    // </hwpText>")]
        sections = [["1. 사업 개요", "가. 공 사 명 : 시험 공장 증설공사(제2026-3101호)\ue003"], ["나. 공사기간 : 2026. 11. ~ 2027. 6."],
                    ["다. 위 치 : 나주시 송월동 일원", "라. 발주자/시공자 : 시험화학 / 시험건설(주)"]]
        want = ("1. 사업 개요 가. 공 사 명 : 시험 공장 증설공사(제2026-3101호) 나. 공사기간 : 2026. 11. ~ 2027. 6. "
                "다. 위 치 : 나주시 송월동 일원 라. 발주자/시공자 : 시험화학 / 시험건설(주)")
        with tempfile.TemporaryDirectory() as d:
            harness = Path(d) / "h.mjs"
            harness.write_text(src + "\nimport { readFileSync } from 'node:fs';\n"
                               "console.log(JSON.stringify(await hwpText(readFileSync(process.argv[2]).toString('base64'))));\n", encoding="utf-8")
            for compressed in (True, False):
                raw = hwp_fixture.build(sections, compressed=compressed)
                f = Path(d) / "t.hwp"
                f.write_bytes(raw)
                r = subprocess.run(["node", str(harness), str(f)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
                got = json.loads(r.stdout)
                self.assertEqual(got["text"], want)
                self.assertEqual(got["chars"], len(want))
                try:
                    import olefile  # noqa: F401  (Actions에는 있음)
                except ImportError:
                    continue
                self.assertEqual(w.hwp_text(raw), want)
            facts = w.attachment_facts(want)
            self.assertEqual(facts.get("공사기간"), "2026. 11. ~ 2027. 6.")

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
