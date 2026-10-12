"""Conservative comparable numbers from previously fetched DART business tables.

Requires (1) two original annual filings from the same issuer, (2) the same
topic, unit and actual table subheading, (3) identical identifying row labels,
(4) unambiguous financial-year header positions, and (5) the later report's
previous-year amount exactly reproduces the earlier report's current-year
amount. Failure on any item means NO numeric-change claim.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST=timezone(timedelta(hours=9))
PERIOD_RE=re.compile(r"제\s*(\d+)\s*기")
EXPLICIT_RE=re.compile(r"(?<!\d)((?:19|20)\d{2})\s*(?:년|[.]12(?:[.]31)?)(?!\d)")
NUMBER_RE=re.compile(r"-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?\Z")
RECEIPT_RE=re.compile(r"\d{14}\Z")
BLACKLIST={"합계","합계액","총계","소계","내수","수출","기타","계"}
SIGNAL_TERMS={
    "productionCapacity":("생산능력",),
    "orderBacklog":("수주상황","수주잔고"),
    "segmentSales":("매출실적","매출현황"),
    "utilization":("가동률",),
}
NEGATIVE_ANCHORS=("생산실적","생산설비","투자계획","설비의신설","투자현황")
MIXED_UNIT_RE=re.compile(r"단위\s*[:：]\s*([^)\n]{1,80})",re.I)
STRIP=re.compile(r"[\s.,ㆍ·/()\[\]'\"-]")


def normalized(value):
    return STRIP.sub("",str(value or "")).lower()


def table_scope(evidence):
    """Recent title-like phrase beats older unrelated keywords in lead-in."""
    ctx=re.sub(r"<[^>]+>"," ",str(evidence.get("context") or ""))
    text=normalized(ctx)
    relevant=set(SIGNAL_TERMS.get(evidence.get("topic"),()))
    terms=[x for words in SIGNAL_TERMS.values() for x in words]+list(NEGATIVE_ANCHORS)
    hits=[(text.rfind(normalized(term)),term) for term in terms if normalized(term) in text]
    if not hits:
        return None
    _,closest=max(hits)
    if closest not in relevant:
        return None
    # Distinguish within a topic: different product/scope tables must not
    # cross-match just because they are both named "매출실적".
    hints=("주요제품군별", "매출유형별", "별도기준", "연결기준",
           "생산능력", "수주상황","가동률","제품별")
    matching=[h for h in hints if normalized(h) in text[-135:]]
    return closest+":"+("+".join(matching[-2:]) if matching else "unspecified")


def clean_unit(evidence):
    unit=evidence.get("unit")
    if not isinstance(unit,str) or not unit.strip():
        return None
    context=re.sub(r"<[^>]+>"," ",str(evidence.get("context") or ""))
    mentions=MIXED_UNIT_RE.findall(context[-270:])
    if mentions:
        last=mentions[-1].strip()
        if "," in last or "，" in last or "및" in last or "/" in last:
            return None
    return unit.strip()


def year_columns(rows,filing_year):
    """Map years to individual numeric columns with exact fiscal headers.

    Prefer explicit YYYY in header, else a sequential Korean '제N기' layout.
    Require consecutive years and no competing header that could reassign
    the value columns.
    """
    possibilities=[]
    for i,row in enumerate(rows[:3]):
        if not isinstance(row,list) or len(row)<3:
            continue
        explicit=[]
        sequence=[]
        for index,cell in enumerate(row):
            years={int(y) for y in EXPLICIT_RE.findall(str(cell))}
            if len(years)==1:
                explicit.append((index,next(iter(years))))
            elif len(years)>1:
                return None
            match=PERIOD_RE.search(str(cell))
            if match:
                sequence.append((index,int(match[1])))
        if len(explicit)>=2 and {filing_year,filing_year-1}.issubset(y for _,y in explicit):
            mapping={y:idx for idx,y in explicit}
            possibilities.append((i,mapping))
        elif len(sequence)>=2 and sequence[0][1]==sequence[1][1]+1:
            # Consecutive period numbering anchored to the annual report year.
            mapping={filing_year-(sequence[0][1]-p):idx for idx,p in sequence}
            if filing_year-1 in mapping and filing_year in mapping:
                possibilities.append((i,mapping))
    if len(possibilities)!=1:
        return None
    return possibilities[0]


def numeric(cell,unit):
    if not isinstance(cell,str):
        return None
    raw=cell.strip().replace(" ","")
    if not NUMBER_RE.fullmatch(raw):
        return None
    if unit=="%":
        if not raw.endswith("%"):
            return None
        raw=raw[:-1]
    elif raw.endswith("%"):
        return None
    try:
        number=Decimal(raw.replace(",",""))
        return number if number.is_finite() else None
    except InvalidOperation:
        return None


def row_ident(row,first_year_col):
    if first_year_col<1 or len(row)<=first_year_col:
        return None
    # Exact pre-year identity fields including region/facility/product.
    labels=[normalized(x) for x in row[:first_year_col]]
    if any(not x for x in labels):
        return None
    if labels[0] in BLACKLIST or len(labels[0])<2:
        return None
    # Require a concrete named product, line, project or operating unit.
    if all(re.fullmatch(r"\d+",x) for x in labels):
        return None
    return tuple(labels)


def extract_current_and_carry(table,year):
    rows=table.get("rows")
    if not isinstance(rows,list):
        return {}
    mapped=year_columns(rows,year)
    if not mapped:
        return {}
    idx,mapping=mapped
    now_idx=mapping.get(year)
    prior_idx=mapping.get(year-1)
    if now_idx is None or prior_idx is None:
        return {}
    # Only accept exactly matching data/header column counts. Real DART
    # colspan tables often shift numeric cells; those need specialized parsers.
    expected=len(rows[idx])
    parsed=defaultdict(list)
    for row in rows[idx+1:]:
        if not isinstance(row,list) or len(row)!=expected:
            continue
        ident=row_ident(row,min(now_idx,prior_idx))
        if ident is None:
            continue
        current=numeric(row[now_idx],table["unit"])
        prior=numeric(row[prior_idx],table["unit"])
        if current is None or prior is None:
            continue
        parsed[ident].append({"year":year,"current":current,"prior":prior,
                              "row":row})
    return {k:items[0] for k,items in parsed.items() if len(items)==1}


def fiscal_period_at_current(table,year):
    rows=table.get("rows") or []
    mapped=year_columns(rows,year)
    if not mapped:
        return None
    i,positions=mapped
    label=rows[i][positions[year]]
    match=PERIOD_RE.search(str(label))
    return int(match[1]) if match else None


def compare_company(record,older_year,year):
    periods=record.get("periods") or {}
    before=periods.get(str(older_year),{})
    after=periods.get(str(year),{})
    if before.get("status")!="evidence_found" or after.get("status")!="evidence_found":
        return []
    receipts=(before.get("receiptNo"),after.get("receiptNo"))
    if not all(isinstance(r,str) and RECEIPT_RE.fullmatch(r) for r in receipts) or receipts[0]==receipts[1]:
        return []
    matches=[]
    old_tables=before.get("tables") or []
    new_tables=after.get("tables") or []
    for topic in SIGNAL_TERMS:
        old=[t for t in old_tables if t.get("topic")==topic and clean_unit(t) and table_scope(t)]
        new=[t for t in new_tables if t.get("topic")==topic and clean_unit(t) and table_scope(t)]
        for a in old:
            for b in new:
                if clean_unit(a)!=clean_unit(b) or table_scope(a)!=table_scope(b):
                    continue
                old_fiscal=fiscal_period_at_current(a,older_year)
                new_fiscal=fiscal_period_at_current(b,year)
                if old_fiscal is not None and new_fiscal is not None and new_fiscal!=old_fiscal+1:
                    continue
                if (old_fiscal is None)!=(new_fiscal is None):
                    continue
                arows=extract_current_and_carry({**a,"unit":clean_unit(a)},older_year)
                brows=extract_current_and_carry({**b,"unit":clean_unit(b)},year)
                for ident in set(arows)&set(brows):
                    old_value=arows[ident]["current"]
                    previous_in_new=brows[ident]["prior"]
                    new_value=brows[ident]["current"]
                    if old_value!=previous_in_new:
                        continue  # Restatement, period change, or wrong table.
                    if new_value==old_value:
                        continue
                    diff=new_value-old_value
                    diff_pct=(diff/old_value*100) if old_value>0 else None
                    matches.append({
                        "company":record["company"],"topic":topic,
                        "unit":clean_unit(a),"scope":table_scope(a),
                        "rowIdentity":list(ident),"fromYear":older_year,
                        "toYear":year,
                        "from":str(old_value),"to":str(new_value),
                        "change":str(diff),
                        "changePercent":float(diff_pct) if diff_pct is not None else None,
                        "carryForwardMatched":True,
                        "originalReceipts":list(receipts),
                        "sourceUrls":[f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r}" for r in receipts],
                        "sourceRows":[arows[ident]["row"],brows[ident]["row"]],
                        "status":"양쪽 공시 원문 동일 행·기간·단위·이월 수치 대조",
                        "journalismStatus":"기보도·기업 원인·사업범위 확인 전 · 단독 아님",
                    })
    # Ambiguous multiple table matches are never accepted by choosing first.
    groups=defaultdict(list)
    for item in matches:
        groups[(item["topic"],tuple(item["rowIdentity"]),item["unit"])].append(item)
    unique=[v[0] for v in groups.values() if len(v)==1]
    unique.sort(key=lambda r:(r["company"],r["topic"],r["rowIdentity"]))
    return unique[:35]


def build(data):
    if not isinstance(data,dict) or not isinstance(data.get("companies"),list):
        raise ValueError("공식 원문 비교 입력 JSON이 올바르지 않음")
    current=int(data["reportYear"])
    previous=int(data["priorYear"])
    if previous!=current-1:
        raise ValueError("연속 회계연도 아님")
    records=[]
    for company in data["companies"]:
        if isinstance(company,dict):
            records.extend(compare_company(company,previous,current))
    return {
        "generatedAt":datetime.now(KST).isoformat(timespec="seconds"),
        "sourceGeneratedAt":data.get("generatedAt"),
        "source":"DART 사업보고서 두 해 원문과 다음 해 보고서 전기 이월값 대조",
        "sourceScope":data.get("scope"),
        "status":"validated_filing_values_not_exclusives",
        "findingCount":len(records),"findings":records,
        "limitations":"회계 수치의 공개 공시 간 차이만 검산. 계약/생산 물량·이익 영향·언론 미보도 사실·단독 여부는 별도 확인",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",default="digests/business_content_latest.json")
    p.add_argument("--output",default="digests/business_metrics_latest.json")
    args=p.parse_args()
    data=json.loads(Path(args.input).read_text(encoding="utf-8"))
    report=build(data)
    path=Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(path)
    print("두 공시 원문·이월 수치 일치한 변화",report["findingCount"],"개; 단독 판정 0건")


if __name__=="__main__":
    main()
