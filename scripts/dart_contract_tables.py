"""Recover *unambiguous* DART contract terms from public document.xml HTML tables.

DART official XML often encodes contract rows as 3 cells:
  <tr><td rowspan=...>2. 계약내역</td><td>계약금액(원)</td><td>...</td></tr>
The older parser discarded every row with a span, creating false blank
"observedFields". Here we ignore decorative spans only when an *explicit*
field label and its immediately adjacent source cell can still be determined.

Never impute values, convert units, infer counterparty from mentions, or
interpret public filed terms as verified actual shipment/revenue.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from html.parser import HTMLParser

# Labels are exact after whitespace/number prefix normalization.
ALIASES={
 "계약금액(원)":"contract_amount",
 "계약금액":"contract_amount",
 "확정계약금액(원)":"contract_amount",
 "확정계약금액":"contract_amount",
 "계약상대방":"counterparty",
 "계약상대방명":"counterparty",
 "계약상대":"counterparty",
 "계약시작일":"contract_start",
 "계약종료일":"contract_end",
 "계약기간시작일":"contract_start",
 "계약기간종료일":"contract_end",
 "계약기간(시작일)":"contract_start",
 "계약기간(종료일)":"contract_end",
 "투자금액(원)":"investment_amount",
 "투자금액":"investment_amount",
 "투자금액총액(원)":"investment_amount",
 "생산재개예정일자":"production_restart",
 "생산재개예정일":"production_restart",
 "생산중단분야":"production_site",
 "사업명":"project",
 "계약명":"project",
}
DATES={"contract_start","contract_end","production_restart"}
AMOUNTS={"contract_amount","investment_amount"}
COMPANY={"counterparty","production_site","project"}
SECRET_MARKERS=("비공개","비공시","공시유보","영업비밀","미공개","미정","보류","해당없음")
BLANKS=("", "-", "－", "—", "N/A", "NA", "미기재", "미정", "없음")
VALIDATED_FIELDS=frozenset(ALIASES.values())


def compact(s):
    return re.sub(r"\s+","",str(s or "")).strip()


def clean_label(s):
    value=compact(s).replace("：",":")
    value=re.sub(r"^(?:\d{1,2}|[가-하])[\.\-]\s*","",value)
    # A direct contract label must be the whole table heading, not just
    # a substring of 'recent sales' or a correction explanation.
    return value.rstrip(":")


def plain(s):
    return " ".join(str(s or "").replace("\u00a0"," ").split()).strip()


class CellTableParser(HTMLParser):
    """Capture each table's own rows without coalescing nested table data."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[]
        self.tables=[]
        self.blocked=0

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in ("script","style"):
            self.blocked+=1
            return
        if self.blocked:return
        if tag=="table":
            if self.stack and self.stack[-1].get("cell") is not None:
                self.stack[-1]["cell"]["nested"]=True
            self.stack.append({"rows":[],"row":None,"cell":None})
            return
        if not self.stack:return
        table=self.stack[-1]
        if tag=="tr":
            table["row"]=[]
        if tag in ("td","th") and table["row"] is not None:
            def count(field):
                raw=attrs.get(field,"1")
                return int(raw) if isinstance(raw,str) and re.fullmatch(r"[1-9]\d{0,2}",raw) else 1
            table["cell"]={"value":[],"colspan":count("colspan"),
                           "rowspan":count("rowspan"),"nested":False}
        if tag in ("br","p","div") and table["cell"] is not None:
            table["cell"]["value"].append(" ")

    def handle_data(self,data):
        if self.stack and not self.blocked and self.stack[-1]["cell"] is not None:
            self.stack[-1]["cell"]["value"].append(data)

    def handle_endtag(self,tag):
        if tag in ("script","style"):
            self.blocked=max(0,self.blocked-1)
            return
        if self.blocked or not self.stack:return
        table=self.stack[-1]
        if tag in ("td","th") and table["row"] is not None and table["cell"] is not None:
            x=table["cell"]
            x["text"]=plain("".join(x.pop("value")))
            table["row"].append(x)
            table["cell"]=None
        elif tag=="tr" and table["row"] is not None:
            if table["row"]:table["rows"].append(table["row"])
            table["row"]=None
        elif tag=="table":
            self.tables.append(self.stack.pop()["rows"])


def _date_value(raw):
    t=compact(raw)
    m=re.fullmatch(r"(20\d{2})[-./년](\d{1,2})[-./월](\d{1,2})일?",t)
    if m:
        y,mo,d=map(int,m.groups())
        try: date(y,mo,d)
        except ValueError:return False
        return True
    if re.fullmatch(r"20\d{6}",t):
        try:date(int(t[:4]),int(t[4:6]),int(t[6:]))
        except ValueError:return False
        return True
    return False


def _value(field,raw):
    v=plain(raw)
    if not v or len(v)>220 or compact(v).upper() in BLANKS:return None
    if any(marker in compact(v) for marker in SECRET_MARKERS):return None
    if field in AMOUNTS:
        # Unit is taken literally from a precisely named row, not guessed.
        # '원' labels are usable when the value itself is numeric.
        if not re.fullmatch(r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?",compact(v)):
            return None
    elif field in DATES:
        if not _date_value(v):return None
    elif field in COMPANY:
        if len(v)>180 or len(v)<2 or re.fullmatch(r"[-_*/\d\s]+",v):
            return None
        # An explanation or legal footnote is not a single counterparty.
        if "※" in v or "\n" in v:return None
    return v


def _label(label, parent=""):
    term=clean_label(label)
    direct=ALIASES.get(term)
    if direct:return direct
    # Subordinate dates cannot be interpreted without an explicit *local*
    # contract-period heading, in the same row or a rowspan parent.
    if "계약기간" in clean_label(parent):
        if term in ("시작일","시작","계약시작"):return "contract_start"
        if term in ("종료일","종료","계약종료"):return "contract_end"
    return None


def _fields_in_table(rows):
    for i,row in enumerate(rows):
        if len(row)>4 or len(row)<2 or any(c["nested"] for c in row):
            continue
        cells=[cell["text"] for cell in row]
        # The sole supported merged form is [explicit section, label, value].
        # A correction comparison row [label, before, after] cannot satisfy
        # this rule because the middle value is never an exact field label.
        if len(row)==3 and all(cell["colspan"]==1 for cell in row):
            field=_label(cells[1],cells[0])
            if field:
                value=_value(field,cells[2])
                if value:yield (field,value,cells[1],"three_cell_explicit_label")
            continue
        if len(row)==2:
            # Multiple row groupings possible; parent context from a table
            # rowspan is handled independently below in _rows_evidence.
            key=_label(cells[0])
            if key:
                value=_value(key,cells[1])
                if value:yield (key,value,cells[0],"two_cell_explicit_label")
            continue
        if len(row)==4 and all(c["colspan"]==1 for c in row):
            # Only independently paired adjacent source columns.
            for label,value in ((cells[0],cells[1]),(cells[2],cells[3])):
                field=_label(label)
                if field:
                    cleaned=_value(field,value)
                    if cleaned:yield (field,cleaned,label,"four_cell_independent_pair")


def _rows_evidence(rows):
    # First collect no-inference adjacent-cell pairs.
    yield from _fields_in_table(rows)
    # Certain DART 2-row period blocks encode:
    # <tr><td rowspan="2">계약기간</td><td>시작일</td><td>date</td></tr>
    # <tr><td>종료일</td><td>date</td></tr>
    # The rowspan is used solely to establish the *local* period context.
    remaining=0
    for row in rows:
        group=remaining>0
        if group:remaining-=1
        if (len(row)==3 and row[0]["rowspan"]>=2 and
            clean_label(row[0]["text"])=="계약기간" and
            all(c["colspan"]==1 for c in row)):
            remaining=min(3,row[0]["rowspan"]-1)
            field=_label(row[1]["text"],"계약기간")
            if field:
                value=_value(field,row[2]["text"])
                if value:yield (field,value,row[1]["text"],"contract_period_rowspan")
        elif (group and len(row)==2 and
              all(c["colspan"]==1 and not c["nested"] for c in row)):
            field=_label(row[0]["text"],"계약기간")
            if field:
                value=_value(field,row[1]["text"])
                if value:yield (field,value,row[0]["text"],"contract_period_rowspan")


def extract_contract_terms(documents):
    """Returns value, literal label, row context and conflict status.

    A field is omitted on any divergent source value; no first-row wins.
    No cross-table/adjacent narrative keyword inference.
    """
    candidates=defaultdict(lambda:defaultdict(list))
    total_tables=0
    for i,markup in enumerate(documents):
        if not isinstance(markup,str) or len(markup)>2_000_000:continue
        reader=CellTableParser()
        try:
            reader.feed(markup)
            reader.close()
        except (ValueError,TypeError):
            continue
        total_tables+=len(reader.tables)
        for table in reader.tables:
            for key,value,label,basis in _rows_evidence(table):
                candidates[key][value].append({
                    "documentIndex":i,
                    "sourceLabel":plain(label)[:100],
                    "rowPattern":basis,
                    "basis":"same_official_table_row"
                })
    fields={}
    proof={}
    conflict=[]
    for key,values in candidates.items():
        if len(values)!=1:
            conflict.append(key)
            continue
        value,examples=next(iter(values.items()))
        fields[key]=value
        proof[key]={"sourceLabel":examples[0]["sourceLabel"],
                    "rowPattern":examples[0]["rowPattern"],
                    "basis":"same_official_table_row",
                    "independentBusinessVerification":False,
                    "distinctDocumentRows":len(examples)}
    return {
        "fields":fields,
        "fieldEvidence":proof,
        "conflictingFields":sorted(conflict),
        "tablesExamined":total_tables,
        "status":"official_table_terms_not_business_effect"
    }
