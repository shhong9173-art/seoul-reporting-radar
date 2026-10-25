import copy
import unittest
from datetime import timedelta
from test_primary_document_dossiers import REG, NOW, fake_fetch
from scripts.primary_document_dossiers import dossier
from scripts.candidate_press_preview import recheck


class CandidatePreviewTests(unittest.TestCase):
    def test_failed_two_checks_preserve_baseline_without_cached_facts(self):
        first = dossier(REG, now=NOW, fetcher=fake_fetch)
        def fail(url):
            raise TimeoutError()
        second = dossier(REG, first, now=NOW+timedelta(hours=1), fetcher=fail)
        third = dossier(REG, second, now=NOW+timedelta(hours=2), fetcher=fail)
        doc = third['cases'][0]['originalDocuments'][0]
        self.assertEqual(doc['lastSuccessfulObservationAt'], first['generatedAt'])
        self.assertIsNone(doc['contentChangedSincePriorCheck'])
        self.assertEqual(third['cases'][0]['factsFromMatchedPrimaryPages'], [])
        last = dossier(REG, third, now=NOW+timedelta(hours=3), fetcher=fake_fetch)
        self.assertEqual(last['cases'][0]['originalDocuments'][0]['comparisonStatus'], 'text_unchanged')

    def test_url_replacement_and_future_baseline_never_comparable(self):
        first = dossier(REG, now=NOW, fetcher=fake_fetch)
        for mutate in ('url', 'time', 'hash'):
            prior = copy.deepcopy(first)
            doc = prior['cases'][0]['originalDocuments'][0]
            if mutate == 'url': doc['url'] += '?different-document=1'
            if mutate == 'time': doc['lastSuccessfulSnapshot']['checkedAt'] = (NOW+timedelta(days=1)).isoformat()
            if mutate == 'hash': doc['lastSuccessfulSnapshot']['contentSha256'] = 'invalid'
            result = dossier(REG, prior, now=NOW+timedelta(hours=1), fetcher=fake_fetch)
            d = result['cases'][0]['originalDocuments'][0]
            self.assertEqual(d['comparisonStatus'], 'first_comparable_observation')

    def test_text_change_is_not_new_publication_or_scoop(self):
        first = dossier(REG, now=NOW, fetcher=fake_fetch)
        later = dossier(REG, first, now=NOW+timedelta(hours=1), fetcher=lambda u: fake_fetch(u)+' Updated footer')
        self.assertEqual(later['cases'][0]['originalDocuments'][0]['comparisonStatus'], 'text_changed_requires_review')
        self.assertEqual(later['cases'][0]['sourceDate'], first['cases'][0]['sourceDate'])
        self.assertFalse(later['cases'][0]['exclusiveConfirmed'])
        self.assertNotEqual(first['verificationRunId'], later['verificationRunId'])

    def test_press_failed_empty_and_bad_shape_distinguished(self):
        def fail(url): raise TimeoutError()
        bad = recheck(['현대차'], now=NOW, fetcher=fail)
        empty = recheck(['현대차'], now=NOW, fetcher=lambda u: '<rss><channel/></rss>')
        html = recheck(['현대차'], now=NOW, fetcher=lambda u: '<html>blocked</html>')
        self.assertEqual(bad['status'], 'search_failed')
        self.assertEqual(empty['rawItemCount'], 0)
        self.assertEqual(empty['status'], 'no_usable_titles_in_response')
        self.assertEqual(html['status'], 'search_failed')
        for r in [bad, empty, html]: self.assertFalse(r['noPriorPressProved'])

    def test_press_dates_title_and_url_not_invented(self):
        def item(date, url='https://news.google.com/rss/articles/one'):
            return '<item><title>현대차 독일 소송</title><link>'+url+'</link><pubDate>'+date+'</pubDate></item>'
        xml='<rss><channel>'+item('Tue, 21 Oct 2025 04:22:00 GMT')+item('')+item('Tue, 21 Oct 2030 04:22:00 GMT')+item('Tue, 21 Oct 2026 04:22:00 GMT','javascript:alert(1)')+'</channel></rss>'
        r=recheck(['현대차', '독일'], now=NOW, fetcher=lambda u: xml)
        self.assertEqual(len(r['items']), 1)
        self.assertEqual(r['rejectedDateCount'], 2)
        self.assertEqual(r['items'][0]['publishedAt'][:10], '2025-10-21')
        self.assertFalse(r['publisherFulltextCompared'])


if __name__ == '__main__': unittest.main()
