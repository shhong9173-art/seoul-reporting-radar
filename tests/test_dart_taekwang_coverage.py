"""태광산업 DART 감시 범위 회귀 테스트(2026-11-04).

기자 명시 출입처 '태광'이 DART 감시(dart_beat_monitor·watchlist)와 회사 고유번호
목록에서 빠져 있었다. 태광산업 법인만 넣고, 이름이 비슷한 다른 법인(태광실업)·
계열사(대한화섬)·해산한 합작사(티엘케미칼)는 넣지 않는다. 같은 이름의 비상장
법인이 공식 목록에 있어도 상장 종목코드가 같은 행으로 증명된 것만 연결한다.
"""
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import dart_beat_monitor as m
import dart_corp_registry as r


def xml(name, code, stock=""):
    return ("<list><corp_name>" + name + "</corp_name><corp_code>" + code +
            "</corp_code><stock_code>" + stock + "</stock_code></list>")


def registry_zip(rows):
    filler = [xml("테스트법인" + str(i), str(i + 10000000)) for i in range(1001)]
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("CORPCODE.xml", "<result>" + "".join(filler + rows) + "</result>")
    return out.getvalue()


class TaekwangScope(unittest.TestCase):
    def test_legal_name_in_chemical_beat_only(self):
        self.assertEqual(m.TARGETS.get("태광산업"), "에너지·화학")
        for other in ("태광", "태광실업", "대한화섬", "티엘케미칼", "태광그룹"):
            self.assertNotIn(other, m.TARGETS)

    def test_committed_code_is_listed_issuer(self):
        codes = json.loads((ROOT / "dart_corp_codes.json").read_text(encoding="utf-8"))["companies"]
        self.assertEqual(codes["태광산업"], {"corp_code": "00153393", "stock_code": "003240"})
        owners = [k for k, v in codes.items() if v.get("corp_code") == "00153393"]
        self.assertEqual(owners, ["태광산업"])

    def test_watchlist_has_legal_name_under_chemicals(self):
        lines = (ROOT / "watchlist.txt").read_text(encoding="utf-8").splitlines()
        start = lines.index("[화학·소재]")
        section = []
        for s in lines[start + 1:]:
            if s.startswith("["):
                break
            section.append(s.strip())
        self.assertIn("태광산업", section)
        self.assertNotIn("태광실업", section)


class TaekwangRegistryIdentity(unittest.TestCase):
    def test_homonym_unlisted_company_does_not_replace_listed_issuer(self):
        idx, total = r.official_index(registry_zip([
            xml("태광산업(주)", "00153393", "003240"),
            xml("주식회사 태광산업", "01234567", ""),
        ]))
        self.assertEqual(idx["태광산업"], {"00153393", "01234567"})
        codes, report = r.resolve({}, idx, registry_count=total)
        self.assertEqual(codes["태광산업"], {"corp_code": "00153393", "stock_code": "003240"})
        row = next(x for x in report["companies"] if x["company"] == "태광산업")
        self.assertEqual(row["status"], "resolved_unique_official_stock_and_legal_name")
        self.assertEqual(row["officialListedStockCodeProof"], "003240")

    def test_existing_code_verified_without_flagging_homonym(self):
        existing = {"태광산업": {"corp_code": "00153393", "stock_code": "003240"}}
        updated, report = r.resolve(existing, {"태광산업": {"00153393", "01234567"}})
        self.assertEqual(updated["태광산업"], existing["태광산업"])
        row = next(x for x in report["companies"] if x["company"] == "태광산업")
        self.assertEqual(row["status"], "existing_code_verified_in_official_registry")

    def test_similar_name_never_matches(self):
        idx, total = r.official_index(registry_zip([
            xml("태광실업", "00888888", ""),
            xml("태광산업개발", "00777777", ""),
        ]))
        codes, report = r.resolve({}, idx, registry_count=total)
        self.assertNotIn("태광산업", codes)
        row = next(x for x in report["companies"] if x["company"] == "태광산업")
        self.assertEqual(row["status"], "no_exact_official_legal_name_match")


if __name__ == "__main__":
    unittest.main()
