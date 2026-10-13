"""Editorial DART-change briefing. Numeric delta != physical output or scoop.

Uses only verified identical-report-period, row-unit and two original receipts.
Creates copy-ready three-bullet Korean PITCH HYPOTHESES, never approved copy.
"""
import argparse,json,re
from datetime import datetime,timedelta,timezone
from pathlib import Path
KST=timezone(timedelta(hours=9))
DART=re.compile(r"^https://dart\.fss\.or\.kr/dsaf001/main\.do\?rcpNo=20\d{12}$")
CATEGORIES={"productionCapacity":"공시상 생산능력 지표",
            "productionActual":"공시상 생산실적 지표",
            "orderBacklog":"공시상 수주잔고 지표",
            "segmentSales":"공시상 부문별 매출 지표"}
MONETARY={"백만원","억원","천원","원"}
QUANTITY={"대","톤","MW","GW","MVA"}

def evaluate(source,metric,now=None,top=8):
 now=now or datetime.now(KST)
 if not 1<=top<=20:raise ValueError("top must be 1..20")
 if (not source.get("generatedAt") or metric.get("sourceGeneratedAt")!=source["generatedAt"]
     or not isinstance(metric.get("items"),list) or not isinstance(metric.get("coverage"),list)):
  raise ValueError("Source and exact-quarter numerical changes are mismatched")
 rows=[]
 for delta in metric["items"]:
  unit=str(delta.get("unit") or "")
  topic=str(delta.get("topic") or "")
  company=str(delta.get("company") or "")
  labels=[str(x).strip() for x in delta.get("rowIdentity",[]) if str(x).strip()]
  urls=delta.get("sourceUrls") or []
  if (topic not in CATEGORIES or unit not in MONETARY|QUANTITY or
      len(urls)!=2 or not all(DART.fullmatch(str(x)) for x in urls)
      or not labels or not company or str(delta.get("period") or "") not in ("03","06","09")):continue
  try:
   pct=float(delta["percentChange"])
   old=float(delta["priorValue"]);new=float(delta["currentValue"])
  except (ValueError,TypeError,KeyError):continue
  if old==0 or abs(pct)<5 or not (-1e7<pct<1e7):continue
  mode="reported_money" if unit in MONETARY else "reported_quantity_unit"
  direction="증가" if new>old else "감소"
  target="·".join(labels[:3])[:96]
  period={"03":"1분기","06":"반기","09":"3분기"}[str(delta["period"])]
  years=str(delta.get("fromYear"))+"년·"+str(delta.get("toYear"))+"년 "+period
  title=company+", "+target+" "+CATEGORIES[topic].replace("공시상 ","")+" "+direction
  # Monetary-capacity rows must not be called production quantity or factory expansion.
  f1=years+" 사업보고서 원문의 동일 사업장·제품·표시단위 대조에서 "+target+" 항목이 "+str(delta["priorValue"])+"→"+str(delta["currentValue"])+"("+unit+")로 "+direction
  f2=("단위가 금액이므로 실물 생산능력·출하량 "+direction+" 사실은 확인되지 않음"
      if mode=="reported_money" else
      "공시된 수량 지표의 변동. 공정·연결범위 및 실제 물량 변동 원인은 미확인")
  f3="기보도·IR 선공개·회계범위·가격/물량 분해 및 기업의 사업 영향 답변 미확인. 원문 검산 후 발제 검토"
  val=min(12,abs(pct)/5)+(9 if topic=="orderBacklog" else 5 if topic=="productionCapacity" else 3)
  # Rank to *review*, not probability. More caution for monetary capacity.
  val-=4 if topic=="productionCapacity" and mode=="reported_money" else 0
  rows.append({"company":company,"topic":topic,"topicLabel":CATEGORIES[topic],
    "rowIdentity":labels,"period":period,"priorValue":str(delta["priorValue"]),
    "currentValue":str(delta["currentValue"]),"percentChange":pct,
    "unit":unit,"unitInterpretation":mode,"sourceUrls":urls,
    "evidenceScoreForReview":round(val,1),"pitchTitle":title,
    "pitchBullets":[f1,f2,f3],
    "sourcePeriod":years,"status":"not_ready_public_documents_only",
    "pressReview":"not_checked","companyResponse":"not_checked",
    "industryImpact":"not_checked","scoopConfirmed":False,
    "publicationApproved":False,
    "reporterQuestions":[
       "실제 동일 제품·연결회사·가격·통화와 회계기간이 완전히 일치하는가?",
       "기보도·IR·실적발표에서 해당 차이가 먼저 공개됐는가?",
       "수요·출하·수주·공정 변화가 실제로 발생했는지 기업이 직접 확인했는가?"]})
 rows.sort(key=lambda r:(-r["evidenceScoreForReview"],-abs(r["percentChange"]),r["company"]))
 # Diverse company / topic; never repeat three similar table rows as separate exclusive stories.
 seen=set();short=[]
 for r in rows:
  key=(r["company"],r["topic"])
  if key in seen:continue
  seen.add(key);short.append(r)
  if len(short)>=top:break
 return {"generatedAt":now.isoformat(timespec="seconds"),
  "sourceGeneratedAt":source["generatedAt"],
  "numericSourceGeneratedAt":metric["generatedAt"],
  "comparedCompanies":metric.get("checkedCompanies"),
  "numericChangesVerified":len(rows),"reportingHypotheses":len(short),
  "shortlist":short,"allRows":rows,
  "confirmedScoops":0,"publicationApproved":0,
  "warning":"기존 공시를 재분석한 취재 가설. 당사자 답변·원문 범위·단가와 수량 분해·기보도 확인 전 발제 보고 금지."}

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--source",default="digests/recent_business_latest.json")
 p.add_argument("--metric",default="digests/recent_metric_changes_latest.json")
 p.add_argument("--output",default="digests/dart_editorial_desk_latest.json")
 a=p.parse_args()
 source=json.loads(Path(a.source).read_text(encoding="utf-8"))
 metrics=json.loads(Path(a.metric).read_text(encoding="utf-8"))
 result=evaluate(source,metrics)
 dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
 tmp=dest.with_suffix(".json.tmp")
 tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 tmp.replace(dest)
 print("DART newsroom review hypotheses",result["reportingHypotheses"],"official rows",result["numericChangesVerified"])
if __name__=="__main__":main()
