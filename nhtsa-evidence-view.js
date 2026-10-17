(function(root){
 'use strict';
 function describe(data,health){
  const items=Array.isArray(data?.items)?data.items:[];
  const snapshot=Date.parse(data?.generatedAt),checked=Date.parse(health?.generatedAt);
  const verified=health?.status==='checked'&&Number.isFinite(snapshot)&&checked===snapshot;
  const failed=health?.status==='source_error'&&Number.isFinite(checked)&&(!Number.isFinite(snapshot)||checked>=snapshot);
  const status=failed?'최신 NHTSA 원천 수집 실패 · 이전 정상자료 보존 · 실제 조사 0건으로 해석 금지':
    verified?'공식 원천 조회 확인':'현재 원천 진단·자료 시각 일치 미확인 · 실제 조사 0건으로 해석 금지';
  return {status:status+' · '+(verified?'확인 자료 ':'보존·참고 자료 ')+items.length+
    '건 · 조사 개시 또는 종결 기록 · 처음 관측 '+(data?.newlyObserved??'미확인')+
    '건(신규 발표 아님) · 원문 변경 '+(data?.changedObserved??'기준점 미생성')+'건',
   rows:items.map(o=>{
    const vehicles=Array.isArray(o.vehicles)?o.vehicles:[];
    const models=[...new Set(vehicles.map(v=>v.make+' '+v.model))].join(', ');
    return {title:o.coveredIssuerRelation+' · '+o.actionNumber+' · '+o.subject,
     text:'개시일 '+o.openedDate+' · 종결일 '+(o.closedDate||'기재 없음')+
      (o.eventDateConflict?' · 원문 날짜 충돌: 단일 사건일 미확정':'')+
      ' · '+(vehicles.length?'원문 차종·연식·부품 조합 '+vehicles.length+'행: '+models:'기존 대표 차종 '+o.model)+
      ' · 종결은 결함 없음 판정이 아님 · 결함 확정/국내 적용 미확인',url:o.sourceUrl};
   })};
 }
 if(typeof module==='object'&&module.exports)module.exports={describe};
 else root.nhtsaEvidenceView={describe};
})(typeof globalThis==='object'?globalThis:this);
