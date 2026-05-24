// Book-wide verification: validateDataset rules + diagram highlight/participant
// checks + implicit-node detection + satisfies/pattern step-ref resolution,
// all against the renderer's current schema. Run: node data/book/_verify.mjs
// (Temporary helper; not shipped — _-prefixed files aren't dataset dirs.)
import fs from 'fs';
import path from 'path';

const BOOK = path.dirname(new URL(import.meta.url).pathname);

function ds(v){return Array.isArray(v)?v.join("\n"):"";}
function isFlow(diag){const f=ds(diag).split("\n").find(l=>l.trim());return /^\s*(graph|flowchart)\b/.test(f||"");}
function extract(d){const s=ds(d),ids=new Set();let m;
  const r1=/(?:^|[\s;])([A-Za-z_][A-Za-z0-9_-]*)\s*(?:\[\(|\(\(|\[\[|\{\{|\[|\(|\{|>)/g;while((m=r1.exec(s)))ids.add(m[1]);
  const r2=/([A-Za-z_][A-Za-z0-9_-]*)\s*(?:--+>|--+|==+>|-\.-+>|<-+>|<--+)\s*(?:\|[^|]*\|\s*)?([A-Za-z_][A-Za-z0-9_-]*)/g;while((m=r2.exec(s))){ids.add(m[1]);ids.add(m[2]);}
  for(const x of["graph","flowchart","subgraph","end","classDef","class","LR","RL","TB","BT","TD"])ids.delete(x);return ids;}
function labelled(diag){const s=ds(diag),set=new Set();let m;const r=/(?:^|[\s;])([A-Za-z_][A-Za-z0-9_-]*)\s*(?:\[\(|\(\(|\[\[|\{\{|\[|\(|\{|>)/g;while((m=r.exec(s)))set.add(m[1]);return set;}
function seq(d){const s=ds(d),ids=new Set();let m;
  const r1=/^\s*(?:participant|actor)\s+([A-Za-z_][A-Za-z0-9_]*)/gm;while((m=r1.exec(s)))ids.add(m[1]);
  const r2=/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:-?->>?|--?>>?|-[)x]|->>|-->>|->|-->)\s*\+?([A-Za-z_][A-Za-z0-9_]*)/gm;while((m=r2.exec(s))){ids.add(m[1]);ids.add(m[2]);}return ids;}
function hasSeqObj(v){return !!(v&&typeof v==="object"&&Array.isArray(v.participants)&&Array.isArray(v.messages));}
function seqObjIds(v){const ids=new Set();for(const p of(v.participants||[])){if(typeof p==="string")ids.add(p);else if(p&&typeof p==="object"){if(p.id)ids.add(p.id);if(p.alias)ids.add(p.alias);}}function walk(msgs){for(const m of(msgs||[])){if(!m||typeof m!=="object")continue;for(const k of["from","to","of","participant","id"])if(m[k])ids.add(m[k]);for(const x of(m.over||[]))ids.add(x);walk(m.messages);if(m.else)walk(m.else.messages);for(const b of(m.branches||[]))walk(b&&b.messages);}}walk(v.messages);return ids;}
function hasDiagram(v){return ds(v).trim()!=="";}
function hasView(v){return !!(v&&typeof v==="object"&&(Array.isArray(v.nodes)||Array.isArray(v.links)||v.mode==="introduced-so-far"));}
function hasStepLike(it){if(!it||typeof it!=="object")return false;const o=Array.isArray(it.options)&&it.options.length>0&&it.options.every(x=>hasView(x.view));return hasView(it.view)||o;}
function refId(v){return typeof v==="string"?v:(v&&typeof v==="object"?v.id:"");}

let problems=0;
const dirs=fs.readdirSync(BOOK).filter(n=>{const p=path.join(BOOK,n);return fs.statSync(p).isDirectory()&&fs.existsSync(path.join(p,'interview.json'));});
for(const dir of dirs){
  const f=path.join(BOOK,dir,'interview.json');
  const d=JSON.parse(fs.readFileSync(f,'utf8'));
  const tag=`[${dir}]`;
  const hasSteps=Array.isArray(d.steps)&&d.steps.length>0;
  const hasCat=Array.isArray(d.patternCatalog)&&d.patternCatalog.length>0;
  if(!hasSteps&&!hasCat){console.log(tag,"no steps[] or patternCatalog[]");problems++;}
  const sids=new Set((d.steps||[]).map(s=>s.id));
  const arch=d.highLevelArchitecture||{};
  if(!Array.isArray(arch.nodes)||!Array.isArray(arch.links)||!Array.isArray(arch.types)){console.log(tag,"missing highLevelArchitecture nodes/links/types arrays");problems++;}
  const nodeIds=new Set((arch.nodes||[]).map(n=>n.id));
  const linkIds=new Set((arch.links||[]).map(l=>l.id));
  const groupIds=new Set((arch.types||[]).map(g=>g.id));
  function checkView(name,view){
    if(!hasView(view))return;
    for(const n of(view.nodes||[])){const id=refId(n);if(id&&!nodeIds.has(id)){console.log(tag,name,"VIEW NODE MISS",id);problems++;}}
    const viewNodeIds=new Set((view.nodes||[]).map(refId).filter(Boolean));
    for(const h of(view.highlight||[]))if(!viewNodeIds.has(h)){console.log(tag,name,"VIEW HL MISS",h);problems++;}
    for(const r of(view.links||[])){
      if(typeof r==="string"&&!linkIds.has(r)){console.log(tag,name,"VIEW LINK MISS",r);problems++;}
      if(r&&typeof r==="object"){for(const id of [r.from,r.to])if(id&&!viewNodeIds.has(id)){console.log(tag,name,"INLINE LINK NODE MISS",id);problems++;}}
    }
    for(const g of(view.groups||[])){const id=refId(g);if(id&&!groupIds.has(id)){console.log(tag,name,"VIEW GROUP MISS",id);problems++;}}
  }
  function checkAny(name,diag,hl){
    if(isFlow(diag)){const ids=extract(diag),lab=labelled(diag);
      for(const h of(hl||[]))if(!ids.has(h)){console.log(tag,name,"HL MISS",h);problems++;}
      for(const id of ids)if(!lab.has(id)){console.log(tag,name,"IMPLICIT node",id);problems++;}
    }else{const ids=seq(diag);for(const h of(hl||[]))if(!ids.has(h)){console.log(tag,name,"SEQ HL MISS",h);problems++;}}
  }
  function checkSequence(name,obj){
    if(!hasSeqObj(obj&&obj.sequence))return;
    const ids=seqObjIds(obj.sequence);
    for(const h of(obj.highlight||obj.sequence.highlight||[]))if(!ids.has(h)){console.log(tag,name,"SEQ HL MISS",h);problems++;}
  }
  if(d.requirementsDiagram)checkAny("reqDiagram",d.requirementsDiagram,[]);
  if(d.capacityDiagram)checkAny("capDiagram",d.capacityDiagram,[]);
	  for(const s of(d.steps||[])){
    if(!hasStepLike(s)){console.log(tag,"step",s.id,"no step-like view");problems++;}
    if(s.diagram){console.log(tag,"step",s.id,"uses diagram instead of view");problems++;}
	    checkView("step "+s.id,s.view);
    for(const o of(s.options||[])){if(o.diagram){console.log(tag,"step",s.id,"option uses diagram instead of view");problems++;}checkView("step "+s.id+" opt",o.view);}
    for(const dd of(s.deepDives||[])){if(dd&&typeof dd==="object"){if(dd.diagram){console.log(tag,"step",s.id,"deep dive uses diagram instead of view");problems++;}checkView("step "+s.id+" deep dive",dd.view);}}
    for(const fl of(s.flows||[])){if(fl.diagram){console.log(tag,"step",s.id,"flow uses diagram instead of sequence");problems++;}if(!hasSeqObj(fl.sequence)){console.log(tag,"step",s.id,"flow missing sequence");problems++;}checkSequence("step "+s.id+" flow",fl);}
    if(s.parent&&!sids.has(s.parent)){console.log(tag,"step",s.id,"unknown parent",s.parent);problems++;}
  }
  if(d.finalDesign){if(!hasStepLike(d.finalDesign)){console.log(tag,"finalDesign no view");problems++;}if(d.finalDesign.diagram){console.log(tag,"finalDesign uses diagram instead of view");problems++;}checkView("finalDesign",d.finalDesign.view);for(const o of(d.finalDesign.options||[])){if(o.diagram){console.log(tag,"finalDesign option uses diagram instead of view");problems++;}checkView("finalDesign opt",o.view);}for(const fl of(d.finalDesign.flows||[])){if(fl.diagram){console.log(tag,"finalDesign flow uses diagram instead of sequence");problems++;}if(!hasSeqObj(fl.sequence)){console.log(tag,"finalDesign flow missing sequence");problems++;}checkSequence("finalDesign flow",fl);}}
  for(const a of(d.api||[])){if(a.diagram){console.log(tag,"api",a.path,"uses diagram instead of sequence");problems++;}checkSequence("api "+a.path,a);}
  for(const grp of["functional","nonFunctional"])for(const it of((d.satisfies||{})[grp]||[]))for(const r of(it.steps||[]))if(!sids.has(r)){console.log(tag,"satisfies ref",r);problems++;}
  for(const p of(d.patterns||[]))for(const r of(p.steps||[]))if(!sids.has(r)){console.log(tag,"pattern ref",r);problems++;}
}
console.log(problems===0?`OK — ${dirs.length} book datasets pass all checks`:`${problems} problems`);
process.exit(problems===0?0:1);
