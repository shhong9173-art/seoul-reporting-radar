import json
import sys
import re
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import executive_article_evidence as ae

BODY = '홍길동 한빛카드 대표는 고객정보 유출 사고의 책임을 지고 사퇴했다. 이 문장은 자동 판정의 경계를 시험하기 위한 가상 회사와 가상 인물의 사례이며 실제 사건을 가리키지 않는다.'
EVENT = re.compile('유출|횡령|기소')


class Evidence(unittest.TestCase):
    def review(self, text, anchors=('한빛카드',)):
        return ae.assess({'status': 'ok', 'body': text}, '홍길동', anchors, EVENT)

    def test_explicit_article_container_only(self):
        raw = '<nav>홍길동 한빛카드 대표는 횡령</nav><div id="dic_area"><p>' + BODY + '</p><aside>다른 사건 횡령</aside></div>'
        result = ae.extract_article(raw)
        self.assertEqual(result['body'], BODY)
        self.assertEqual(ae.extract_article('<div class="article-cont"><figure>사진 설명</figure><p>' + BODY + '</p></div>')['body'], BODY)
        self.assertEqual(ae.extract_article('<body>' + BODY + '</body>')['status'], 'body_missing')

    def test_jsonld_and_description_not_body(self):
        obj = {'@type': 'NewsArticle', 'articleBody': BODY}
        self.assertEqual(ae.extract_article('<script type="application/ld+json">' + json.dumps(obj) + '</script>')['body'], BODY)
        obj = {'@type': 'NewsArticle', 'description': BODY}
        self.assertEqual(ae.extract_article('<script type="application/ld+json">' + json.dumps(obj) + '</script>')['status'], 'body_missing')

    def test_body_context_is_only_link_not_guilt(self):
        r = self.review(BODY)
        self.assertEqual(r['status'], 'context_linked')
        self.assertLessEqual(len(r['excerpt']), 120)
        self.assertNotIn('body', r)
        self.assertEqual(len(r['bodyHash']), 64)

    def test_other_paragraph_and_other_company_not_connected(self):
        for text in ('홍길동 한빛카드 대표는 신제품을 발표했다. 김아무 씨는 횡령으로 기소됐다.',
                     '홍길동 다른카드 대표는 유출 사고 책임을 지고 사퇴했다. 한빛카드는 신제품을 냈다.',
                     '홍길동 한빛카드 대표는 신제품을 발표했다.\n유출 사고가 발생했다.',
                     '홍길동 한빛카드 대표는 김아무의 횡령 혐의를 지적했다.'):
            self.assertEqual(self.review(text)['status'], 'context_unconfirmed')

    def test_prefix_companies_and_names(self):
        self.assertEqual(self.review('홍길동 GS리테일 대표는 유출로 기소됐다.', ('GS',))['status'], 'context_unconfirmed')
        self.assertEqual(self.review('김홍길동 한빛카드 대표는 유출로 기소됐다.')['status'], 'context_unconfirmed')

    def test_speaker_and_exoneration_require_manual_review(self):
        self.assertEqual(self.review('홍길동 한빛카드 대표는 “유출을 막자”고 말했다.')['status'], 'context_unconfirmed')
        self.assertEqual(self.review('홍길동 한빛카드 대표는 유출 혐의로 기소됐다. 홍길동 한빛카드 대표는 이후 무죄 판결을 받았다.')['status'], 'outcome_requires_review')

    def test_failed_fetch_never_uses_title_snippet(self):
        r = ae.assess({'status': 'fetch_failed', 'body': BODY}, '홍길동', ['한빛카드'], EVENT)
        self.assertEqual(r['status'], 'fetch_failed')
        self.assertNotIn('excerpt', r)

    def test_bounded_review_deduplicates_fetch_not_identity(self):
        calls = []
        def fetch(url):
            calls.append(url)
            return {'status': 'ok', 'body': BODY}
        r = ae.Reviewer(fetch, 1)
        self.assertEqual(r.review('one', '홍길동', ['한빛카드'], EVENT, 'now')['status'], 'context_linked')
        self.assertEqual(r.review('one', '다른사람', ['한빛카드'], EVENT, 'now')['status'], 'context_unconfirmed')
        self.assertEqual(r.review('two', '홍길동', ['한빛카드'], EVENT, 'now')['status'], 'budget_exhausted')
        self.assertEqual(calls, ['one'])

    def test_supported_public_urls_only(self):
        for url in ('http://127.0.0.1/', 'https://localhost/', 'https://news.naver.com.evil.test/', 'file:///tmp/key', 'https://user:pass@news.naver.com/'):
            self.assertFalse(ae.allowed_url(url))
        self.assertTrue(ae.allowed_url('https://n.news.naver.com/article/001/123'))

    def test_redirect_and_response_limits(self):
        class Response:
            status_code = 302
            headers = {'Location': 'http://127.0.0.1/private'}
            encoding = 'utf-8'
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def iter_content(self, size): yield b'x' * (ae.MAX_BYTES + 1)
        calls = []
        def get(url, **kw):
            calls.append(url)
            self.assertFalse(kw['allow_redirects'])
            return Response()
        self.assertEqual(ae.fetch_article('https://www.inews24.com/view/1', get=get)['status'], 'unsupported_source')
        self.assertEqual(len(calls), 1)
        Response.status_code = 403
        self.assertEqual(ae.fetch_article('https://www.inews24.com/view/1', get=get)['status'], 'http_error')
        Response.status_code = 200
        Response.headers = {'Content-Type': 'text/html'}
        self.assertEqual(ae.fetch_article('https://www.inews24.com/view/1', get=get)['status'], 'too_large')

    def test_failure_keeps_diagnostic(self):
        def fail(*args, **kwargs): raise TimeoutError()
        self.assertEqual(ae.fetch_article('https://www.inews24.com/view/1', get=fail)['status'], 'fetch_failed')

    def test_previous_budget_pending_has_priority(self):
        r = ae.Reviewer(lambda url: {'status': 'ok', 'body': BODY}, 1, priority=['waiting'])
        self.assertEqual(r.review('earlier', '홍길동', ['한빛카드'], EVENT, 'now')['status'], 'budget_exhausted')
        self.assertEqual(r.review('waiting', '홍길동', ['한빛카드'], EVENT, 'now')['status'], 'context_linked')


    def test_public_hosts_outside_list_need_global_addresses(self):
        def resolver(addr):
            return lambda host, port, proto=0: [(2, 1, 6, "", (addr, port))]
        self.assertTrue(ae.allowed_url("https://www.the-today.com/news/articleView.html?idxno=1", resolver("211.43.203.9")))
        for addr in ("10.0.0.5", "127.0.0.1", "169.254.169.254", "192.168.0.2", "::1"):
            self.assertFalse(ae.allowed_url("https://news.example-press.kr/a/1", resolver(addr)), addr)
        def broken(host, port, proto=0):
            raise OSError("dns")
        self.assertFalse(ae.allowed_url("https://news.example-press.kr/a/1", broken))
        self.assertFalse(ae.allowed_url("https://8.8.8.8/a/1", resolver("8.8.8.8")))             # IP 직접 입력 금지
        self.assertFalse(ae.allowed_url("https://intranet.local/a/1", resolver("8.8.8.8")))
        self.assertFalse(ae.allowed_url("https://press.kr:8443/a/1", resolver("8.8.8.8")))       # 다른 포트 금지

    def test_redirect_to_private_address_is_blocked(self):
        class Response:
            status_code = 302
            headers = {'Location': 'https://cdn.example-press.kr/x'}
            encoding = 'utf-8'
            def __enter__(self): return self
            def __exit__(self, *args): pass
        calls = []
        def get(url, **kw):
            calls.append(url)
            return Response()
        def resolver(host, port, proto=0):
            return [(2, 1, 6, "", ("10.1.2.3" if host.startswith("cdn.") else "211.43.203.9", port))]
        self.assertEqual(ae.fetch_article('https://www.example-press.kr/a/1', get=get, resolve=resolver)['status'], 'unsupported_source')
        self.assertEqual(calls, ['https://www.example-press.kr/a/1'])

if __name__ == '__main__':
    unittest.main()
