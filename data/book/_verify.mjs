// Book-wide verification: validateDataset rules + diagram highlight/participant
// checks + implicit-node detection + satisfies/pattern step-ref resolution,
// all against the renderer's exact regex. Run: node data/book/_verify.mjs
// (Temporary helper; not shipped — _-prefixed files aren't dataset dirs.)
import fs from 'fs';
import path from 'path';

const BOOK = path.dirname(new URL(import.meta.url).pathname);

function ds(v){return Array.isArray(v)?v.join("\n"):(typeof v==="string"?v:"");}
function isFlow(diag){const f=ds(diag).split("\n").find(l=>l.trim());return /^\s*(graph|flowchart)\b/.test(f||"");}
function extract(d){const s=ds(d),ids=new Set();let m;
  const r1=/(?:^|[\s;])([A-Za-z_][A-Za-z0-9_-]*)\s*(?:\[\(|\(\(|\[\[|\{\{|\[|\(|\{|>)/g;while((m=r1.exec(s)))ids.add(m[1]);
  const r2=/([A-Za-z_][A-Za-z0-9_-]*)\s*(?:--+>|--+|==+>|-\.-+>|<-+>|<--+)\s*(?:\|[^|]*\|\s*)?([A-Za-z_][A-Za-z0-9_-]*)/g;while((m=r2.exec(s))){ids.add(m[1]);ids.add(m[2]);}
  for(const x of["graph","flowchart","subgraph","end","classDef","class","LR","RL","TB","BT","TD"])ids.delete(x);return ids;}
function labelled(diag){const s=ds(diag),set=new Set();let m;const r=/(?:^|[\s;])([A-Za-z_][A-Za-z0-9_-]*)\s*(?:\[\(|\(\(|\[\[|\{\{|\[|\(|\{|>)/g;while((m=r.exec(s)))set.add(m[1]);return set;}
function seq(d){const s=ds(d),ids=new Set();let m;
  const r1=/^\s*(?:participant|actor)\s+([A-Za-z_][A-Za-z0-9_]*)/gm;while((m=r1.exec(s)))ids.add(m[1]);
  const r2=/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:-?->>?|--?>>?|-[)x]|->>|-->>|->|-->)\s*\+?([A-Za-z_][A-Za-z0-9_]*)/gm;while((m=r2.exec(s))){ids.add(m[1]);ids.add(m[2]);}return ids;}
function hasDiagram(v){return ds(v).trim()!=="";}
function hasStepLike(it){if(!it||typeof it!=="object")return false;const o=Array.isArray(it.options)&&it.options.length>0&&it.options.every(x=>hasDiagram(x.diagram));return hasDiagram(it.diagram)||o;}

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
  function checkAny(name,diag,hl){
    if(isFlow(diag)){const ids=extract(diag),lab=labelled(diag);
      for(const h of(hl||[]))if(!ids.has(h)){console.log(tag,name,"HL MISS",h);problems++;}
      for(const id of ids)if(!lab.has(id)){console.log(tag,name,"IMPLICIT node",id);problems++;}
    }else{const ids=seq(diag);for(const h of(hl||[]))if(!ids.has(h)){console.log(tag,name,"SEQ HL MISS",h);problems++;}}
  }
  if(d.requirementsDiagram)checkAny("reqDiagram",d.requirementsDiagram,[]);
  if(d.capacityDiagram)checkAny("capDiagram",d.capacityDiagram,[]);
  for(const s of(d.steps||[])){
    if(!hasStepLike(s)){console.log(tag,"step",s.id,"no step-like diagram");problems++;}
    if(s.diagram)checkAny("step "+s.id,s.diagram,s.highlight);
    for(const o of(s.options||[]))if(o.diagram)checkAny("step "+s.id+" opt",o.diagram,o.highlight);
    for(const fl of(s.flows||[]))if(fl.diagram)checkAny("step "+s.id+" flow",fl.diagram,fl.highlight);
    if(s.parent&&!sids.has(s.parent)){console.log(tag,"step",s.id,"unknown parent",s.parent);problems++;}
  }
  if(d.finalDesign){if(!hasStepLike(d.finalDesign)){console.log(tag,"finalDesign no diagram");problems++;}if(d.finalDesign.diagram)checkAny("finalDesign",d.finalDesign.diagram,d.finalDesign.highlight);}
  for(const a of(d.api||[]))if(a.diagram)checkAny("api "+a.path,a.diagram,a.highlight||[]);
  for(const grp of["functional","nonFunctional"])for(const it of((d.satisfies||{})[grp]||[]))for(const r of(it.steps||[]))if(!sids.has(r)){console.log(tag,"satisfies ref",r);problems++;}
  for(const p of(d.patterns||[]))for(const r of(p.steps||[]))if(!sids.has(r)){console.log(tag,"pattern ref",r);problems++;}
}
console.log(problems===0?`OK — ${dirs.length} book datasets pass all checks`:`${problems} problems`);
process.exit(problems===0?0:1);
