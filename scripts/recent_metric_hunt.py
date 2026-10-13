"""Strict SAME-PERIOD OpenDART tabular delta for /hunt reporting research.

Only numbers with exact company, comparable half/quarter, named source row,
identical explicit table unit and source URLs enter result. This records
reported figure changes, not produced goods, causal demand or a scoop.
"""
import json,argparse,re
from decimal import Decimal,InvalidOperation
from pathlib import Path
from datetime import datetime,timedelta,timezone
KST=timezone(timedelta(hours=9))
TOPICS=("productionCapacity","productionActual","orderBacklog","segmentSales")
RECEIPT=re.compile(r"^20\d{12}$")
NUMBER=re.compile(r"^-?\d{1,3}(?:,\d{3})*(?:\.\d+)?$|^-?\d+(?:\.\d+)?$")
UNITS={"백만원","천원","억원","원","대","톤","MW","GW","MVA"}
def num(value):
    v=str(value or "").strip()
    if not NUMBER.fullmatch(v):return None
    try:return Decimal(v.replace(",",""))
    except (InvalidOperation,ValueError):return None

def norm(v):
    return re.sub(r"\s+","",str(v or "")).lower()

def rows(tables):
    found={}
    duplicates=set()
    for table in tables:
        if table.get("topic") not in TOPICS or table.get("unit") not in UNITS:
            continue
        for values in (table.get("rows") or [])[1:]:
            if not isinstance(values,list) or len(values)<4:continue
            metrics=[num(x) for x in values[-3:]]
            if any(x is None for x in metrics):continue
            labels=tuple(norm(x) for x in values[:-3])
            if not labels or any(not t or len(t)>150 for t in labels):continue
            key=(table["topic"],table["unit"],labels)
            if key in found:duplicates.add(key)
            else:found[key]={"value":metrics[0],"priorYear":metrics[1],
                             "sourceRow":values,"unit":table["unit"],
                             "topic":table["topic"],"labels":values[:-3]}
    for key in duplicates:found.pop(key,None)
    return found

def evaluate(source,now=None):
    now=now or datetime.now(KST)
    if not isinstance(source.get("companies"),list):
        raise ValueError("Recent DART verified company records missing")
    report=[]
    coverage=[]
    for issuer in source["companies"]:
        company=issuer.get("company")
        a=issuer.get("priorSamePeriod") or {}
        b=issuer.get("current") or {}
        valid=(issuer.get("status")=="official_sections_retrieved"
               and a.get("status")=="evidence_found" and b.get("status")=="evidence_found"
               and a.get("period")==b.get("period")
               and str(a.get("year"))==str(int(b.get("year") or 0)-1)
               and a.get("period") in ("03","06","09")
               and RECEIPT.fullmatch(str(a.get("receiptNo") or ""))
               and RECEIPT.fullmatch(str(b.get("receiptNo") or "")))
        if not valid:
            coverage.append({"company":company,"status":"not_comparable",
                             "reason":"원문·회계기간·접수번호 검증 부족"})
            continue
        old=rows(a.get("tables") or [])
        current=rows(b.get("tables") or [])
        matched=0
        for key in sorted(set(old)&set(current)):
            before,after=old[key],current[key]
            # one named line, same reporting period, same numerical unit.
            if before["value"]==after["value"]:continue
            if before["value"]==0:continue # no meaningful YoY percentage
            shift=after["value"]-before["value"]
            pct=round(float(shift/before["value"]*100),2)
            if abs(pct)<5:continue # publication includes many tiny shifts
            matched+=1
            report.append({
                "company":company,"topic":after["topic"],"rowIdentity":after["labels"],
                "priorValue":str(before["value"]),"currentValue":str(after["value"]),
                "diff":str(shift),"percentChange":pct,
                "unit":after["unit"],
                "period":b["period"],
                "fromYear":a["year"],"toYear":b["year"],
                "originalReceipts":[a["receiptNo"],b["receiptNo"]],
                "sourceUrls":[
                    "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+a["receiptNo"],
                    "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+b["receiptNo"]],
                "sourceRows":[before["sourceRow"],after["sourceRow"]],
                "evidenceStatus":"동일 기업·분기/반기·표시단위·행명 일치 검증",
                "reportingStatus":"공시상 숫자 변동만 확인; 생산 물량·실제 사업영향·기보도/단독 미확인",
                "priority":"business_document_diff_reporter_review"})
        coverage.append({"company":company,"status":"same_period_rows_checked",
                         "rowsCompared":len(set(old)&set(current)),"changes":matched})
    report.sort(key=lambda x:(-abs(x["percentChange"]),x["company"]))
    return {"generatedAt":now.isoformat(timespec="seconds"),
        "sourceGeneratedAt":source.get("generatedAt"),
        "sourcePeriod":source.get("businessYear"),
        "officialChanges":len(report),
        "items":report[:60],
        "coverage":coverage,
        "checkedCompanies":sum(x["status"]=="same_period_rows_checked" for x in coverage),
        "scoopConfirmed":0,
        "warning":"발췌된 일부 사업표의 첫 보고연도 숫자 비교. 공시 숫자 변화≠물량/가격/가동률 변화. 표 구성·단위/연결범위 최종 원문 확인 필요"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",default="digests/recent_business_latest.json")
    p.add_argument("--out",default="digests/recent_metric_changes_latest.json")
    args=p.parse_args()
    report=evaluate(json.loads(Path(args.source).read_text(encoding="utf-8")))
    if report["checkedCompanies"]<1:raise ValueError("no comparable official source rows")
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(path)
    print("DART same-period numeric changes",report["officialChanges"],
          "companies compared",report["checkedCompanies"],"scoop count 0")
if __name__=="__main__":main()
