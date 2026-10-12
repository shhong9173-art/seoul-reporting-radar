"""정정 공시가 직접 제시한 전후 표만 비교한다. 원공시 대조나 단독 판정은 아니다."""
import re
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urlsplit, parse_qs


class Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.tables = [], []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag == 'table':
            for table in self.stack:
                table['ambiguous'] = True
            self.stack.append({'rows': [], 'row': None, 'cell': None, 'ambiguous': bool(self.stack)})
        if not self.stack:
            return
        table = self.stack[-1]
        if tag == 'tr':
            table['row'] = []
        if tag in ('td', 'th', 'te', 'tu'):
            table['cell'] = []
            # Reject spanned comparison rows instead of shifting a value's column.
            table['span'] = attrs.get('rowspan', '1') != '1' or attrs.get('colspan', '1') != '1'
        if tag in ('br', 'p') and table['cell'] is not None:
            table['cell'].append(' ')

    def handle_data(self, data):
        if self.stack and not self.hidden and self.stack[-1]['cell'] is not None:
            self.stack[-1]['cell'].append(data)

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        if not self.stack:
            return
        table = self.stack[-1]
        if tag in ('td', 'th', 'te', 'tu') and table['cell'] is not None:
            if table['row'] is not None:
                table['row'].append((' '.join(''.join(table['cell']).split()), table['span']))
            table['cell'] = None
        if tag == 'tr' and table['row'] is not None:
            table['rows'].append(table['row'])
            table['row'] = None
        if tag == 'table':
            self.tables.append(self.stack.pop())


def compact(text):
    return re.sub(r'\s+', '', text)


def valid_date(text):
    match = re.fullmatch(r'\s*(\d{4})[-./년]\s*(\d{1,2})[-./월]\s*(\d{1,2})일?\s*', text)
    if not match:
        return None
    try:
        return date(*map(int, match.groups())).isoformat()
    except ValueError:
        return None


def compare_correction(markup, source_url):
    result = {'status': 'comparison_unavailable', 'basis': 'issuer_correction_table',
              'originalDocumentVerified': False, 'sourceUrl': source_url,
              'correctionDate': None, 'referencedFilingDate': None,
              'changes': [], 'unchangedCount': 0, 'skippedRows': 0}
    url = urlsplit(source_url)
    if url.scheme != 'https' or url.hostname != 'dart.fss.or.kr' or url.path not in ('/report/viewer.do', '/dsaf001/main.do') or not re.fullmatch(r'\d{14}', parse_qs(url.query).get('rcpNo', [''])[0]):
        result['reason'] = 'unverified_source_url'
        return result
    parser = Tables()
    parser.feed(markup)
    header_seen = False
    for table in parser.tables:
        if table['ambiguous']:
            result['skippedRows'] += len(table['rows'])
            continue
        header = None
        for row in table['rows']:
            cells = [cell for cell, _ in row]
            keys = [compact(cell) for cell in cells]
            if len(cells) == 2:
                if keys[0] == '정정일자':
                    result['correctionDate'] = valid_date(cells[1])
                if '공시서류제출일' in keys[0] or '최초제출일' in keys[0]:
                    result['referencedFilingDate'] = valid_date(cells[1])
            if '정정전' in keys and '정정후' in keys and any(k in ('정정항목','항목') for k in keys):
                if any(span for _, span in row) or len(set(keys)) != len(keys):
                    result['skippedRows'] += 1
                    header = None
                    continue
                header_seen = True
                header = {key: keys.index(key) for key in keys}
                continue
            if header is None:
                continue
            if len(cells) != len(header) or any(span for _, span in row):
                result['skippedRows'] += 1
                continue
            field = cells[header.get('정정항목', header.get('항목'))]
            before, after = cells[header['정정전']], cells[header['정정후']]
            if not field or not before or not after:
                result['skippedRows'] += 1
                continue
            if compact(before) == compact(after):
                result['unchangedCount'] += 1
                continue
            category = 'text_review'
            for pattern, label in ((r'생산재개|생산중단일', 'production_schedule'),
                                   (r'계약.*금액|투자금액', 'amount'),
                                   (r'계약상대|계약대상', 'contract_party'),
                                   (r'계약기간', 'contract_period'),
                                   (r'생산능력', 'capacity'),
                                   (r'이사회|증빙서류', 'formal_review')):
                if re.search(pattern, field):
                    category = label
                    break
            result['changes'].append({'field': field, 'before': before, 'after': after,
                                      'category': category, 'sourceUrl': source_url,
                                      'beforeUnspecified': before in ('-', '미정', '미기재'),
                                      'afterUnspecified': after in ('-', '미정', '미기재')})
    result['status'] = ('issuer_reported_changes' if result['changes'] else
                        'no_comparable_change' if header_seen else 'comparison_unavailable')
    return result


def public_correction_details(numeric):
    comparisons = (numeric or {}).get('correctionComparisons', [])
    details = []
    for comparison in comparisons:
        if comparison.get('status') != 'issuer_reported_changes':
            continue
        for change in comparison.get('changes', []):
            # Full evidence stays in numeric JSON; this is a labelled UI excerpt.
            def excerpt(value):
                return value if len(value) <= 180 else value[:180] + '… [발췌]'
            details.append(f"정정표 기재 · {change['field']}: {excerpt(change['before'])} → {excerpt(change['after'])} (원공시 별도 대조 전·단독 아님)")
    return details[:6]
