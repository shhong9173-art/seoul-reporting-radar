"""Private feed client: 204 means nothing stored, other errors are never read as empty."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import private_store as ps  # noqa: E402


class R:
    def __init__(self, code, body=None):
        self.status_code, self.body = code, body

    def json(self):
        return self.body


class PrivateStore(unittest.TestCase):
    def test_get_put_and_errors(self):
        seen = {}
        def get(url, headers, timeout):
            seen["url"], seen["auth"] = url, headers["Authorization"]
            return R(204)
        self.assertIsNone(ps.get("page-watch", "tok", get=get))
        self.assertTrue(seen["url"].endswith("/ingest/page-watch"))
        self.assertEqual(seen["auth"], "Bearer tok")
        self.assertEqual(ps.get("us-comments", "t", get=lambda u, headers, timeout: R(200, {"a": 1})), {"a": 1})
        with self.assertRaises(ps.StoreError):
            ps.get("us-comments", "t", get=lambda u, headers, timeout: R(404))
        with self.assertRaises(ValueError):
            ps.get("anything", "t", get=get)
        self.assertEqual(ps.put("partner-filings", {"x": "한글"}, "t", post=lambda u, data, headers, timeout: R(200)), 200)

    def test_whole_connector_url_in_the_secret_still_works(self):
        tok = "FAKEtoken_0123456789abcdefghij-XYZ"  # not a real credential
        self.assertEqual(ps.normalize_token(f"https://example.workers.dev/mcp/{tok}"), tok)
        self.assertEqual(ps.normalize_token(f" {tok}\n"), tok)
        self.assertEqual(ps.normalize_token(f'"{tok}"'), tok)
        seen = {}
        ps.get("page-watch", f"https://example.workers.dev/mcp/{tok}/", get=lambda u, headers, timeout: seen.update(h=headers) or R(204))
        self.assertEqual(seen["h"]["Authorization"], f"Bearer {tok}")


if __name__ == "__main__":
    unittest.main()
