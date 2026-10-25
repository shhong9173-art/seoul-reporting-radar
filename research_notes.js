/* Personal reporter annotations. No network, no automatic score/novelty changes. */
(function(root){
"use strict";
const KEY="industry-radar.research-notes.v1";
const STATES=["미검토","실제 발제함","추가 취재 필요","이미 보도됨","출입처 아님","가치 낮음","원문 오류"];
function validate(value){
 if(!value||value.version!==1||!Array.isArray(value.entries)||value.entries.length>2000)
  throw Error("메모 파일 형식 또는 최대 2,000건 제한을 확인하세요");
 const seen=new Set();
 const entries=value.entries.map(r=>{
  if(!r||typeof r.id!=="string"||!r.id||r.id.length>2000||seen.has(r.id)||
   typeof r.starred!=="boolean"||!STATES.includes(r.state)||
   typeof r.note!=="string"||r.note.length>4000||
   typeof r.updatedAt!=="string"||!/^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/.test(r.updatedAt)||
   !Number.isFinite(Date.parse(r.updatedAt)))throw Error("유효하지 않은 메모 항목");
  seen.add(r.id);
  return {id:r.id,starred:r.starred,state:r.state,note:r.note,updatedAt:r.updatedAt};
 });
 return {version:1,entries};
}
function load(storage){
 const raw=storage.getItem(KEY);
 return raw===null?{version:1,entries:[]}:validate(JSON.parse(raw));
}
function get(book,id){return book.entries.find(r=>r.id===id)||{id,starred:false,state:"미검토",note:"",updatedAt:null};}
function save(storage,book,entry,now=new Date()){
 const candidate=validate({version:1,entries:[...book.entries.filter(r=>r.id!==entry.id),
  {...entry,updatedAt:now.toISOString()}]});
 storage.setItem(KEY,JSON.stringify(candidate));
 return candidate; // Update UI state only after storage succeeds.
}
function merge(storage,book,imported){
 const incoming=validate(imported),all=new Map(book.entries.map(r=>[r.id,r]));
 for(const row of incoming.entries){
  const old=all.get(row.id);
  if(!old||Date.parse(row.updatedAt)>Date.parse(old.updatedAt))all.set(row.id,row);
 }
 const candidate=validate({version:1,entries:[...all.values()]});
 storage.setItem(KEY,JSON.stringify(candidate));return candidate;
}
const api={KEY,STATES,validate,load,get,save,merge};
if(typeof module!=="undefined"&&module.exports)module.exports=api;
root.ResearchNotes=api;
})(typeof window!=="undefined"?window:globalThis);
