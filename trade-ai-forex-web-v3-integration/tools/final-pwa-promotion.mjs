import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import {execFileSync} from 'node:child_process'
import {fileURLToPath} from 'node:url'
import {root,original,inventory,sha,payloadPaths} from './release-package.mjs'

export const packageDir=path.join(root,'release/final-pwa-56cbd7e-revision2')
const actual=p=>fs.existsSync(p)?sha(fs.readFileSync(p)):null
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b)
const inside=(r,p)=>{const x=path.relative(path.resolve(r),path.resolve(p));return x!==''&&!x.startsWith('..')&&!path.isAbsolute(x)}
const order=['src/analysis/contract.ts','src/analysis/client.ts','src/AnalysisPanel.css','src/AnalysisNewsRisk.tsx','src/CalendarPanel.tsx','src/MarketChart.tsx','src/RiskCalculator.tsx','src/AnalysisPanel.tsx','src/App.tsx']
function safe(dir,file){
 if(!payloadPaths.includes(file)&&!inventory(dir).includes(file))throw new Error('BLOCK unlisted path')
 const p=path.resolve(dir,file)
 if(!inside(dir,p))throw new Error('BLOCK path traversal')
 noLinks(p);return p
}
function noLinks(p){for(let x=path.resolve(p);;x=path.dirname(x)){
 if(fs.existsSync(x)&&fs.lstatSync(x).isSymbolicLink())throw new Error('BLOCK symlink/junction')
 if(x===path.dirname(x))break
}}
function allowedTarget(target){
 if(path.resolve(target)!==path.resolve(original)&&!inside(path.join(root,'.artifacts'),target))throw new Error('BLOCK target root')
 noLinks(target)
}
function manifest(pkg){
 noLinks(pkg);const bytes=fs.readFileSync(path.join(pkg,'manifest.json'))
 if(sha(bytes)!==fs.readFileSync(path.join(pkg,'manifest.sha256'),'utf8').trim())throw new Error('BLOCK manifest hash')
 const m=JSON.parse(bytes)
 if(m.format!==2||m.target_root!==original||m.mode!=='DRY_RUN_DEFAULT'||
    !same(m.files.map(f=>f.file).sort(),payloadPaths)||!same(m.guards.map(g=>g.file).sort(),m.guard_inventory))
  throw new Error('BLOCK manifest identity/allowlist/coverage')
 return {m,digest:sha(bytes)}
}
export function dryRun(pkg=packageDir,target=original){
 allowedTarget(target);const {m,digest}=manifest(pkg)
 if(!same(inventory(target),m.guard_inventory))throw new Error('BLOCK target inventory drift')
 for(const g of m.guards)if(actual(safe(target,g.file))!==g.sha256)throw new Error('BLOCK target guard drift: '+g.file)
 for(const f of m.files){
  if(actual(safe(path.join(pkg,'payload'),f.file))!==f.source_sha256)throw new Error('BLOCK payload hash: '+f.file)
  if(actual(safe(target,f.file))!==f.expected_target_sha256)throw new Error('BLOCK destination hash: '+f.file)
 }
 return {status:m.deployment_readiness,mode:'DRY_RUN',writes:0,deletes:0,files:m.files.length,guards:m.guards.length,manifest_sha256:digest}
}
function approval(approved,expected,digest){if(approved!==true||expected!==digest)throw new Error('BLOCK new operator approval and exact manifest required')}
function saveReceipt(backup,r){const data=JSON.stringify(r,null,2)+'\n';fs.writeFileSync(path.join(backup,'receipt.json'),data);fs.writeFileSync(path.join(backup,'receipt.sha256'),sha(data))}
function state(r,m){
 const expected=[...new Set([...m.guard_inventory,...r.files.filter(f=>fs.existsSync(path.join(r.target,f.file))).map(f=>f.file)])].sort()
 if(!same(inventory(r.target),expected))throw new Error('BLOCK concurrent inventory drift')
 const writes=new Set(r.files.map(f=>f.file))
 for(const g of m.guards)if(!writes.has(g.file)&&actual(safe(r.target,g.file))!==g.sha256)throw new Error('BLOCK protected file drift')
 for(const f of r.files){const h=actual(safe(r.target,f.file));if(h!==f.before&&h!==f.after)throw new Error('BLOCK concurrent user edit: '+f.file)}
}
function atomic(dest,bytes,expected){
 noLinks(dest);if(actual(dest)!==expected)throw new Error('BLOCK concurrent destination drift')
 fs.mkdirSync(path.dirname(dest),{recursive:true})
 const tmp=path.join(path.dirname(dest),'.final-pwa-'+crypto.randomUUID()+'.tmp'),fd=fs.openSync(tmp,'wx')
 try{fs.writeFileSync(fd,bytes);fs.fsyncSync(fd)}finally{fs.closeSync(fd)}
 if(actual(dest)!==expected)throw new Error('BLOCK concurrent destination drift; temporary retained')
 fs.renameSync(tmp,dest);if(actual(dest)!==sha(bytes))throw new Error('BLOCK post-write hash')
}
export function rollback({pkg=packageDir,backup,operatorApproved=false,expectedManifest}){
 const {m,digest}=manifest(pkg);approval(operatorApproved,expectedManifest,digest)
 if(!inside(root,backup))throw new Error('BLOCK backup root');noLinks(backup)
 const bytes=fs.readFileSync(path.join(backup,'receipt.json'))
 if(sha(bytes)!==fs.readFileSync(path.join(backup,'receipt.sha256'),'utf8').trim())throw new Error('BLOCK receipt hash')
 const r=JSON.parse(bytes);allowedTarget(r.target)
 if(r.manifest!==digest||!same(r.files.map(f=>f.file).sort(),payloadPaths))throw new Error('BLOCK receipt identity')
 for(const f of r.files){
  const expected=m.files.find(x=>x.file===f.file)
  if(f.before!==expected.expected_target_sha256||f.after!==expected.source_sha256)throw new Error('BLOCK receipt content')
  noLinks(path.join(backup,'before',f.file))
  if(f.before!==null&&actual(path.join(backup,'before',f.file))!==f.before)throw new Error('BLOCK corrupt backup')
 }
 state(r,m)
 for(const f of [...r.files].reverse()){
  state(r,m);const dest=safe(r.target,f.file)
  if(actual(dest)===f.before)continue
  if(f.before===null){
   if(actual(dest)!==f.after)throw new Error('BLOCK rollback user change')
   const retained=path.join(backup,'retained-new-files',f.file);noLinks(retained)
   if(fs.existsSync(retained))throw new Error('BLOCK retained collision')
   fs.mkdirSync(path.dirname(retained),{recursive:true});fs.renameSync(dest,retained)
  }else atomic(dest,fs.readFileSync(path.join(backup,'before',f.file)),f.after)
 }
 if(r.files.some(f=>actual(path.join(r.target,f.file))!==f.before))throw new Error('BLOCK restore hash')
 r.status='ROLLED_BACK';saveReceipt(backup,r);return {status:r.status,deletes:0,backup}
}
export async function applyRelease({pkg=packageDir,target=original,backupRoot=path.join(root,'release/final-pwa-backups'),operatorApproved=false,expectedManifest,smoke,beforeReplace}){
 const {m,digest}=manifest(pkg);approval(operatorApproved,expectedManifest,digest);allowedTarget(target)
 if(!inside(root,backupRoot)||inside(target,backupRoot)||path.resolve(target)===path.resolve(backupRoot))throw new Error('BLOCK backup location')
 noLinks(backupRoot)
 if(typeof smoke!=='function')throw new Error('BLOCK smoke required')
 if(path.resolve(target)===path.resolve(original)){
  if(m.deployment_readiness!=='READY_FOR_PWA_APPROVAL')throw new Error('BLOCK release not ready')
  // Fresh read-only OS/source/startup/loaded fingerprint/proxy guard; no service actions.
  execFileSync(path.join(root,'.artifacts/cutover/runtime-venv/Scripts/python.exe'),['-B',path.join(root,'tools/final-pwa-release.py'),'guard'],{cwd:root,windowsHide:true,stdio:'pipe'})
 }
 dryRun(pkg,target)
 const buffers=new Map(m.files.map(f=>[f.file,fs.readFileSync(safe(path.join(pkg,'payload'),f.file))]))
 for(const f of m.files)if(sha(buffers.get(f.file))!==f.source_sha256)throw new Error('BLOCK payload changed during read')
 const backup=path.join(backupRoot,crypto.randomUUID());fs.mkdirSync(backup,{recursive:true})
 const r={format:2,target:path.resolve(target),manifest:digest,status:'PREPARED',files:order.map(file=>{
  const f=m.files.find(x=>x.file===file);return {file,before:f.expected_target_sha256,after:f.source_sha256}
 })}
 for(const f of r.files)if(f.before!==null){
  const bytes=fs.readFileSync(safe(target,f.file));if(sha(bytes)!==f.before)throw new Error('BLOCK backup drift')
  const dest=path.join(backup,'before',f.file);fs.mkdirSync(path.dirname(dest),{recursive:true});fs.writeFileSync(dest,bytes,{flag:'wx'})
  if(actual(dest)!==f.before)throw new Error('BLOCK backup verification')
 }
 saveReceipt(backup,r);dryRun(pkg,target)
 try{
  for(const [index,f] of r.files.entries()){
   if(beforeReplace)await beforeReplace({index,file:f.file,target})
   state(r,m);atomic(safe(target,f.file),buffers.get(f.file),f.before)
  }
  state(r,m)
  if(r.files.some(f=>actual(path.join(target,f.file))!==f.after))throw new Error('BLOCK applied hashes')
  if(await smoke({target,backup})!==true)throw new Error('BLOCK smoke failed')
  r.status='APPLIED_SMOKE_PASS';saveReceipt(backup,r);return {status:r.status,backup,deletes:0,files:r.files.length}
 }catch(error){
  r.status='FAILED_SAFE_STOP';saveReceipt(backup,r)
  try{rollback({pkg,backup,operatorApproved,expectedManifest})}catch(restore){throw new Error('BLOCK rollback review: '+restore.message+'; '+error.message)}
  throw new Error('ROLLED_BACK: '+error.message)
 }
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 if(process.argv.length!==2)throw new Error('BLOCK CLI is DRY_RUN only; live APPLY needs a separately approved orchestration')
 console.log(JSON.stringify(dryRun(),null,2))
}
