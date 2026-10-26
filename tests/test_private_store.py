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


if __name__ == "__main__":
    unittest.main()
