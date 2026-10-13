"""Combine cached public-source evidence without claiming exclusives."""
import json
from pathlib import Path
from datetime import datetime,timezone,timedelta
def build(sources):
 feeds=[];leads=[]
 for name,data,key in sources:
  ready=bool(data.get("generatedAt") and isinstance(data.get(key),list))
  rows=data.get(key,[]) if ready else []
  feeds.append({"name":name,"status":"ready" if ready else "missing",
                "rows":len(rows) if ready else None,"generatedAt":data.get("generatedAt") if ready else None})
  for row in rows[:15]:
   if name=="DART":
    for p in row.get("projects",[])[:3]:
     leads.append({"source":name,"headline":str(row.get("company"))+" "+str(p.get("project")),
       "fact":"공시상 종료 예정월 변경","url":(p.get("originalUrls") or [None])[-1],
       "verification":"실제 준공 일정과 기업 답변 필요"})
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
            ("NHTSA",get("nhtsa_official_latest.json"),"records")])
 p=Path("digests/industry_official_hunt_latest.json")
 tmp=p.with_suffix(".json.tmp");tmp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");tmp.replace(p)
if __name__=="__main__":main()
