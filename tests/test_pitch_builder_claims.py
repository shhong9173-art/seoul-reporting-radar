"""pitch_builder must extract numbers and never republish stale template facts."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def item(n, title, summary, source, hours=2, category="전력기기"):
    published = (datetime.now(timezone.utc) - timedelta(hours=hours + n)).isoformat()
    return {"title": title, "summary": summary, "sourceName": source, "category": category,
            "url": f"https://news.example.com/{n}", "published": published}


def run_builder(items):
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(ROOT / "pitch_builder.py", tmp)
        Path(tmp, "data.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run([sys.executable, "-I", "pitch_builder.py"], cwd=tmp,
                              capture_output=True, text=True, timeout=60)
        if proc.returncode:
            raise AssertionError(proc.stderr)
        return json.loads(Path(tmp, "pitch.json").read_text(encoding="utf-8")), proc.stdout


class PitchBuilderClaims(unittest.TestCase):
    def test_number_regex_is_not_double_escaped(self):
        src = (ROOT / "pitch_builder.py").read_text(encoding="utf-8")
        line = next(l for l in src.splitlines() if l.startswith("NUM_RE="))
        ns = {"re": __import__("re")}
        exec(line, ns)
        self.assertEqual(ns["NUM_RE"].findall("계약 1,812억원 규모, 점유율 30% 증가"), ["1,812억원", "30%"])

    def test_stale_template_numbers_are_dropped_when_evidence_lacks_them(self):
        # Trigger the LS Electric data-center template with a different, real-looking
        # current contract: the template's fixed 1812억원/345kV/9개/2030년 must not appear.
        rows = [item(i, f"LS일렉트릭, 미국 AI 데이터센터 변압기 공급 {i}", "LS일렉트릭이 데이터센터용 변압기 500억원 공급 계약",
                     f"매체{i}") for i in range(4)]
        pitches, out = run_builder(rows)
        self.assertEqual(pitches, [])
        self.assertIn("1812억원", out)
        self.assertIn("dropped): 1", out)

    def test_template_without_fixed_facts_keeps_evidence_numbers(self):
        rows = [
            item(0, "정부, ESS 확대 대책 발표", "산업부가 ESS 보급 확대와 전력망 보강 대책을 내놨다", "정책신문", category="재생에너지"),
            item(1, "LS일렉트릭, ESS 배전 사업 1,000억원 투자", "LS일렉트릭이 ESS와 배전 설비에 1,000억원 투자", "매체A"),
            item(2, "HD현대일렉트릭, 변압기 ESS 수주 30% 증가", "HD현대일렉트릭 ESS·변압기 수주가 30% 늘었다", "매체B"),
        ]
        pitches, out = run_builder(rows)
        self.assertEqual(len(pitches), 1, out)
        p = pitches[0]
        self.assertIn("1,000억원", p["numbers"])
        self.assertNotIn("unsupportedClaims", p)
        blob = json.dumps(p, ensure_ascii=False)
        for stale in ("1812억원", "6765억원", "3.87조", "8400억원", "4.4조"):
            self.assertNotIn(stale, blob)

    def test_order_wording_is_not_share_price_noise(self):
        src = (ROOT / "pitch_builder.py").read_text(encoding="utf-8")
        line = next(l for l in src.splitlines() if l.startswith("NOISE_RE="))
        ns = {"re": __import__("re")}
        exec(line, ns)
        self.assertIsNone(ns["NOISE_RE"].search("HD현대일렉트릭 변압기 수주가 30% 늘었다"))
        self.assertIsNotNone(ns["NOISE_RE"].search("HD현대일렉트릭 주가 급등"))

    def test_clean_title_strips_prefix_and_publisher(self):
        rows = [
            item(0, "[단독] 정부, ESS 확대 대책 발표 - 정책신문", "산업부 ESS 전력망 대책", "정책신문", category="재생에너지"),
            item(1, "LS일렉트릭, ESS 배전 사업 1,000억원 투자 - 매체A", "LS일렉트릭 ESS 배전 1,000억원 투자", "매체A"),
            item(2, "HD현대일렉트릭, 변압기 ESS 수주 30% 증가 - 매체B", "HD현대일렉트릭 ESS 변압기 수주 30%", "매체B"),
        ]
        pitches, _ = run_builder(rows)
        titles = [e["title"] for e in pitches[0]["evidence"]]
        self.assertTrue(all(not t.startswith("[단독]") and not t.endswith("매체A") for t in titles), titles)


if __name__ == "__main__":
    unittest.main()
