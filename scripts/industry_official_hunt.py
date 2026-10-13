"""Combine cached public-source evidence without claiming exclusives."""
import json
from pathlib import Path
from datetime import datetime,timezone,timedelta
def build(sources):
 feeds=[];leads=[]
 for name,data,key in sources:
  ready=bool(data.get("generatedAt") and isinstance(data.get(key),list))
  rows=data.get(key,[]) if ready else []
  checks=data.get("checks",[]) if isinstance(data.get("checks"),list) else []
  failures=sum(x.get("status")=="source_error" for x in checks)
  success=sum(x.get("status")=="checked" for x in checks)
  feeds.append({"name":name,"status":("partial" if ready and failures else "ready" if ready else "missing"),
                "rows":len(rows) if ready else None,"generatedAt":data.get("generatedAt") if ready else None,
                "checkedQueries":success if checks else None,"failedQueries":failures if checks else None})
  for row in rows[:15]:
   if name=="DART":
    for p in row.get("projects",[])[:3]:
     leads.append({"source":name,"headline":str(row.get("company"))+" "+str(p.get("project")),
       "fact":"공시상 종료 예정월 변경","url":(p.get("originalUrls") or [None])[-1],
       "verification":"실제 준공 일정과 기업 답변 필요"})
   elif name=="DART_METRIC":
    if not (row.get("sourceUrls") and len(row["sourceUrls"])==2):continue
    leads.append({"source":name,
      "headline":str(row.get("company"))+" · "+"/".join(row.get("rowIdentity",[])[:2]),
      "fact":"공식 "+str(row.get("fromYear"))+"→"+str(row.get("toYear"))+
             " 동일기간·단위 숫자 "+str(row.get("priorValue"))+" → "+str(row.get("currentValue"))+
             " ("+str(row.get("unit"))+")",
      "url":row["sourceUrls"][-1],
      "verification":"원문 숫자 변동과 실제 물량·생산능력 확대·기보도/기업 설명 구분"})
   elif name=="CUSTOMS_FIVE":
    leads.append({"source":name,"headline":str(row.get("name")),
      "fact":"관세청 구분별 공개 집계("+str(row.get("period"))+") · 기업 실적 아님",
      "url":row.get("sourceUrl"),"verification":"시도·성질/국가별 모집단·단위 확인"})
   elif name=="NHTSA":
    leads.append({"source":name,"headline":str(row.get("make"))+" "+str(row.get("model"))+" "+str(row.get("id")),
      "fact":"이미 공개된 미국 "+str(row.get("kind")),"url":row.get("officialApi"),
      "verification":"한국 판매차 관련성 및 당국 조사 별도 검증"})
   elif name=="CUSTOMS":
    leads.append({"source":name,"headline":str(row.get("label")),
      "fact":"HS4 전국 통계·기업 수출 아님","url":row.get("sourceUrl"),
      "verification":"동일기간·단가·HS 세부품목 대조"})
   elif name=="OVERSEAS" and row.get("nameVerified"):
    leads.append({"source":name,"headline":str(row.get("title")),
      "fact":"공식 문서 명시적 법인명 언급","url":row.get("sourceUrl"),
      "verification":"공장·수주·낙찰 확정 전 원문 확인"})
 for name in ("NTIS 연구과제","나라장터 공공조달"):
  feeds.append({"name":name,"status":"not_connected","rows":None})
 return {"generatedAt":datetime.now(timezone(timedelta(hours=9))).isoformat(),
   "feeds":feeds,"leads":leads,"confirmedScoops":0,"status":"research_only"}
def main():
 def get(name):
  try:return json.loads((Path("digests")/name).read_text(encoding="utf-8"))
  except (OSError,ValueError):return {}
 doc=build([("DART",get("investigation_hunt_latest.json"),"investigations"),
            ("OVERSEAS",get("overseas_official_latest.json"),"documents"),
            ("CUSTOMS",get("hs_trends_latest.json"),"items"),
            ("NHTSA",get("nhtsa_official_latest.json"),"records"),
            ("DART_METRIC",get("recent_metric_changes_latest.json"),"items"),
            ("CUSTOMS_FIVE",{"generatedAt":get("customs_five_latest.json").get("generatedAt"),
                             "items":get("customs_five_latest.json").get("services")},"items")])
 p=Path("digests/industry_official_hunt_latest.json")
 tmp=p.with_suffix(".json.tmp");tmp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");tmp.replace(p)
if __name__=="__main__":main()
