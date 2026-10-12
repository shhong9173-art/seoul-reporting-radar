import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
import scoop_scout as scoop


class BeatIdentityTests(unittest.TestCase):
    def test_explicit_chemical_beats_are_present(self):
        for name in ('태광', '동성케미칼', 'DL케미칼'):
            self.assertEqual(scoop.direct_beat_company_hits({}, name+' 공장 증설'), [name])

    def test_unconfirmed_beats_remain_monitoring_only(self):
        for name in ('세아씨엠','동국씨엠','효성중공업','일진전기'):
            self.assertIn(name, scoop.target_hits(name+' 공장 증설'))
            self.assertEqual(scoop.direct_beat_company_hits({},name+' 공장 증설'), [])

    def test_global_brands_are_not_korean_entities(self):
        for name in ('BMW','Audi','아우디','Volkswagen','폭스바겐'):
            self.assertEqual(scoop.direct_beat_company_hits({},name+' 독일 공장 생산 조정'), [])
        for title, entity in (('BMW Korea 생산 조정','BMW코리아'),('Audi Korea 리콜','아우디코리아'),('Volkswagen Korea 서비스','폭스바겐코리아')):
            self.assertEqual(scoop.direct_beat_company_hits({}, title), [entity])

    def test_affiliate_names_do_not_create_parent_hits(self):
        for title, expected in (('POSCO Future M 투자',[]),('포스코퓨처엠 투자',[]),('POSCO International 투자',[]),('POSCO Holdings 투자',['포스코홀딩스']),('GS Caltex 투자',['GS칼텍스']),('OCI Holdings 투자',['OCI홀딩스'])):
            self.assertEqual(scoop.direct_beat_company_hits({},title), expected)

    def test_separately_named_parent_survives(self):
        self.assertEqual(set(scoop.direct_beat_company_hits({},'POSCO Holdings와 POSCO의 공동 투자')), {'포스코홀딩스','포스코'})

    def test_short_names_and_affiliate_suffixes(self):
        for title in ('태광산업 투자','태광실업 투자','Taekwang Industrial 투자','LS전선아시아 계약','GS리테일 투자','OCI페로 투자','POSCO인터내셔널 투자','BIGS 투자','SOCIAL 투자'):
            self.assertEqual(scoop.direct_beat_company_hits({},title), [])

    def test_korean_particles_and_english_aliases(self):
        for title, entity in (('현대차는 공장 증설','현대차'),('태광의 공장','태광'),('DL Chemical 투자','DL케미칼'),('GS와 공급 계약','GS'),('LS MnM 투자','LS MnM')):
            self.assertIn(entity,scoop.direct_beat_company_hits({},title))

    def test_query_hint_and_spoofed_hosts_do_not_assign_company(self):
        for url in ('https://example.com/a','https://bmw.co.kr.example.com/a','https://example.com/bmw.co.kr'):
            self.assertEqual(scoop.direct_beat_company_hits({'querySite':'bmw.co.kr','url':url},'BMW 독일 투자'), [])

    def test_actual_korean_official_host_supplies_context(self):
        self.assertEqual(scoop.direct_beat_company_hits({'url':'https://www.bmw.co.kr/a'},'서비스 공지'), ['BMW코리아'])
        self.assertEqual(scoop.direct_beat_company_hits({'url':'https://bmw.com/a'},'BMW 독일 투자'), [])

    def test_issuer_affiliate_and_supplier_remain_out_of_beat(self):
        for issuer in ('삼성전기','포스코퓨처엠','Taekwang Industrial'):
            self.assertEqual(scoop.direct_beat_company_hits({'corpName':issuer},'신규시설투자'), [])

    def test_parent_site_cannot_override_named_affiliate(self):
        self.assertEqual(scoop.direct_beat_company_hits({'url':'https://www.posco.com/a'},'POSCO Future M 투자'), [])

    def test_user_spelling_of_mercedes_korea(self):
        self.assertEqual(scoop.direct_beat_company_hits({},'메르세데스-벤츠 코리아 리콜'), ['메르세데스벤츠코리아'])
