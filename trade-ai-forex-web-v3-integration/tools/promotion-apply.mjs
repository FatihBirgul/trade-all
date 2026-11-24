import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import {fileURLToPath} from 'node:url'
import {execFileSync} from 'node:child_process'
import {root,original,payloadPaths,sha,inventory} from './release-package.mjs'
import {dryRun} from './promotion-dry-run.mjs'

export const rcManifestSha='1035c98420554d268c32f1a38bd0ed19379c18a67c53d93362edee216105b715'
const deploymentOrder=['src/analysis/contract.ts','src/analysis/client.ts','src/AnalysisPanel.css','src/AnalysisPanel.tsx','src/AnalysisNewsRisk.tsx','src/CalendarPanel.tsx','src/MarketChart.tsx','src/RiskCalculator.tsx','src/App.tsx']
const actual=p=>fs.existsSync(p)?sha(fs.readFileSync(p)):null
const inside=(parent,p)=>{const rel=path.relative(path.resolve(parent),path.resolve(p));return rel!==''&&!rel.startsWith('..')&&!path.isAbsolute(rel)}
function noLinks(p) {
 for(let current=path.resolve(p);;current=path.dirname(current)) {
  if(fs.existsSync(current)&&fs.lstatSync(current).isSymbolicLink())throw new Error('BLOCK symlink/junction')
  if(current===path.dirname(current))break
 }
}
function allowedTarget(target) {
 if(path.resolve(target)!==path.resolve(original)&&!inside(path.join(root,'.artifacts'),target))throw new Error('BLOCK target root')
 noLinks(target)
}
function approvalCheck(approval,expectedManifest) {
 if(approval!==true)throw new Error('BLOCK explicit operator approval required')
 if(expectedManifest!==rcManifestSha)throw new Error('BLOCK exact approved manifest required')
}
function saveReceipt(dir,receipt) {
 const data=JSON.stringify(receipt,null,2)+'\n'
 fs.writeFileSync(path.join(dir,'receipt.json'),data)
 fs.writeFileSync(path.join(dir,'receipt.sha256'),sha(data)+'\n')
}
function atomicReplace(destination,bytes,expected) {
 noLinks(destination)
 if(actual(destination)!==expected)throw new Error('BLOCK concurrent target drift')
 fs.mkdirSync(path.dirname(destination),{recursive:true})
 const temporary=path.join(path.dirname(destination),'.v3-cutover-'+crypto.randomUUID()+'.tmp')
 const fd=fs.openSync(temporary,'wx')
 try {fs.writeFileSync(fd,bytes);fs.fsyncSync(fd)}finally{fs.closeSync(fd)}
 if(actual(destination)!==expected)throw new Error('BLOCK concurrent target drift; temporary retained')
 fs.renameSync(temporary,destination)
 if(actual(destination)!==sha(bytes))throw new Error('BLOCK post-write hash mismatch')
}
function verifyCurrent(receipt) {
 allowedTarget(receipt.target)
 if(receipt.manifest_sha256!==rcManifestSha||JSON.stringify(receipt.files.map(f=>f.file).sort())!==JSON.stringify(payloadPaths))throw new Error('BLOCK receipt identity')
 const sealed=fs.readFileSync(path.join(root,'release/rc/manifest.json'))
 if(sha(sealed)!==rcManifestSha)throw new Error('BLOCK approved RC unavailable')
 const approved=JSON.parse(sealed)
 if(JSON.stringify(receipt.guards)!==JSON.stringify(approved.guards)||JSON.stringify(receipt.guard_inventory)!==JSON.stringify(approved.guard_inventory))throw new Error('BLOCK receipt guards')
 for(const f of receipt.files) {
  const expected=approved.files.find(e=>e.file===f.file)
  if(f.before_sha256!==expected.expected_target_sha256||f.after_sha256!==expected.source_sha256)throw new Error('BLOCK receipt file hashes')
 }
 const current=inventory(receipt.target)
 const expected=[...new Set([...receipt.guard_inventory,...receipt.files.filter(f=>fs.existsSync(path.join(receipt.target,f.file))).map(f=>f.file)])].sort()
 if(JSON.stringify(current)!==JSON.stringify(expected))throw new Error('BLOCK rollback inventory drift')
 const writes=new Set(receipt.files.map(f=>f.file))
 for(const g of receipt.guards)if(!writes.has(g.file)&&actual(path.join(receipt.target,g.file))!==g.sha256)throw new Error('BLOCK protected file drift')
 for(const f of receipt.files) {
  const h=actual(path.join(receipt.target,f.file))
  if(h!==f.before_sha256&&h!==f.after_sha256)throw new Error('BLOCK user changes; rollback review required: '+f.file)
 }
}
export function rollbackRelease({backup,approval=false,expectedManifest}) {
 approvalCheck(approval,expectedManifest);noLinks(backup)
 if(!inside(root,backup))throw new Error('BLOCK backup root')
 const data=fs.readFileSync(path.join(backup,'receipt.json'))
 if(sha(data)!==fs.readFileSync(path.join(backup,'receipt.sha256'),'utf8').trim())throw new Error('BLOCK receipt integrity')
 const receipt=JSON.parse(data)
 verifyCurrent(receipt)
 for(const f of receipt.files)if(f.before_sha256!==null) {noLinks(path.join(backup,'before',f.file));if(actual(path.join(backup,'before',f.file))!==f.before_sha256)throw new Error('BLOCK backup corruption')}
 receipt.status='ROLLING_BACK';saveReceipt(backup,receipt)
 for(const f of [...receipt.files].reverse()) {
  const dest=path.join(receipt.target,f.file),h=actual(dest)
  if(h===f.before_sha256)continue
  if(f.before_sha256===null) {
   noLinks(dest)
   if(actual(dest)!==f.after_sha256)throw new Error('BLOCK concurrent rollback drift')
   const retained=path.join(backup,'retained-new-files',f.file)
   fs.mkdirSync(path.dirname(retained),{recursive:true})
   if(fs.existsSync(retained))throw new Error('BLOCK retained backup collision')
   fs.renameSync(dest,retained)
  } else atomicReplace(dest,fs.readFileSync(path.join(backup,'before',f.file)),f.after_sha256)
  f.restored=true;saveReceipt(backup,receipt)
 }
 for(const f of receipt.files)if(actual(path.join(receipt.target,f.file))!==f.before_sha256)throw new Error('BLOCK restore hash mismatch')
 receipt.status='ROLLED_BACK';saveReceipt(backup,receipt)
 return {status:receipt.status,backup,files:receipt.files.length,deletes:0}
}
export async function applyRelease({packageDir,target=original,backupRoot=path.join(root,'release/live-backups'),approval=false,expectedManifest,smoke,beforeReplace}) {
 approvalCheck(approval,expectedManifest);allowedTarget(target);noLinks(packageDir);noLinks(backupRoot)
 if(!inside(root,backupRoot)||inside(target,backupRoot)||path.resolve(target)===path.resolve(backupRoot))throw new Error('BLOCK backup location')
 if(typeof smoke!=='function')throw new Error('BLOCK smoke callback required')
 if(actual(path.join(packageDir,'manifest.json'))!==expectedManifest)throw new Error('BLOCK source manifest changed')
 dryRun(packageDir,target)
 const manifest=JSON.parse(fs.readFileSync(path.join(packageDir,'manifest.json')))
 const buffers=new Map(manifest.files.map(f=>[f.file,fs.readFileSync(path.join(packageDir,'payload',f.file))]))
 for(const f of manifest.files)if(sha(buffers.get(f.file))!==f.source_sha256)throw new Error('BLOCK payload changed')
 const backup=path.join(backupRoot,new Date().toISOString().replace(/[:.]/g,'-')+'-'+crypto.randomUUID())
 fs.mkdirSync(backupRoot,{recursive:true});fs.mkdirSync(backup)
 const receipt={format:1,target:path.resolve(target),manifest_sha256:expectedManifest,status:'PREPARED',guard_inventory:manifest.guard_inventory,guards:manifest.guards,files:deploymentOrder.map(file=>manifest.files.find(f=>f.file===file)).map(f=>({file:f.file,before_sha256:f.expected_target_sha256,after_sha256:f.source_sha256,applied:false}))}
 for(const f of receipt.files)if(f.before_sha256!==null) {
  const bytes=fs.readFileSync(path.join(target,f.file))
  if(sha(bytes)!==f.before_sha256)throw new Error('BLOCK backup target drift')
  const dest=path.join(backup,'before',f.file);fs.mkdirSync(path.dirname(dest),{recursive:true});fs.writeFileSync(dest,bytes,{flag:'wx'})
  if(actual(dest)!==f.before_sha256)throw new Error('BLOCK backup verification')
 }
 saveReceipt(backup,receipt)
 // Validate the complete target again after backups and before the first write.
 dryRun(packageDir,target)
 try {
  receipt.status='APPLYING';saveReceipt(backup,receipt)
  for(const [index,f] of receipt.files.entries()) {
   if(beforeReplace)await beforeReplace({index,file:f.file,target,backup})
   verifyCurrent(receipt)
   atomicReplace(path.join(target,f.file),buffers.get(f.file),f.before_sha256)
   f.applied=true;saveReceipt(backup,receipt)
  }
  verifyCurrent(receipt)
  for(const f of receipt.files)if(actual(path.join(target,f.file))!==f.after_sha256)throw new Error('BLOCK applied hash mismatch')
  if(await smoke({target,backup})!==true)throw new Error('BLOCK smoke failed')
  receipt.status='APPLIED_SMOKE_PASS';saveReceipt(backup,receipt)
  return {status:receipt.status,backup,files:receipt.files.length}
 }catch(error) {
  receipt.status='FAILED_SAFE_STOP';saveReceipt(backup,receipt)
  let restored
  try {restored=rollbackRelease({backup,approval,expectedManifest})}
  catch(rollbackError) {throw Object.assign(new Error('Safe stop: '+rollbackError.message+'; original error: '+error.message),{backup})}
  throw Object.assign(new Error('APPLY failed; '+restored.status+': '+error.message),{backup})
 }
}

async function liveSmoke() {
 const response=await fetch('http://127.0.0.1:5173/src/AnalysisPanel.tsx',{signal:AbortSignal.timeout(10000)})
 if(!response.ok||!(await response.text()).includes('Manuel Forex analizi'))return false
 const schema=await (await fetch('http://127.0.0.1:5173/engine/openapi.json',{signal:AbortSignal.timeout(10000)})).text()
 return schema.includes('broker_contract')&&schema.includes('spread_status')
}
function requireBackendReadiness(file) {
 if(!file||!inside(path.join(root,'release/cutover'),file))throw new Error('BLOCK exact backend acceptance receipt required')
 noLinks(file)
 const proof=JSON.parse(fs.readFileSync(file,'utf8'))
 if(proof.status!=='PASS'||proof.source_head!=='56cbd7e05a40b106deda9298e2be28b488d0d952'||proof.numpy!=='2.2.6'||proof.port!==8006||proof.execution_permission!==false||!proof.loaded?.loaded_function_code_sha256||!Number.isInteger(proof.pid))throw new Error('BLOCK backend readiness not verified')
 const age=Date.now()-Date.parse(proof.accepted_at_utc)
 if(!Number.isFinite(age)||age<0||age>120000)throw new Error('BLOCK stale backend acceptance')
 if(!proof.runtime_manifest||!inside(path.join(root,'.artifacts/cutover'),proof.runtime_manifest))throw new Error('BLOCK runtime manifest location')
 noLinks(proof.runtime_manifest)
 const raw=fs.readFileSync(proof.runtime_manifest),startup=JSON.parse(raw)
 if(sha(raw)!==proof.runtime_manifest_sha256||startup.pid!==proof.pid||startup.port!==8006||startup.source_head!==proof.source_head||startup.numpy!==proof.numpy||startup.loaded.loaded_function_code_sha256!==proof.loaded.loaded_function_code_sha256)throw new Error('BLOCK runtime manifest mismatch')
 const command="$backendOwner = Get-NetTCPConnection -LocalPort 8006 -State Listen | Select-Object -ExpandProperty OwningProcess; $backendProcess = Get-CimInstance Win32_Process -Filter \"ProcessId = $backendOwner\"; @{pid=$backendOwner; created_at_utc=$backendProcess.CreationDate.ToUniversalTime().ToString('o')} | ConvertTo-Json -Compress"
 const output=JSON.parse(execFileSync('powershell.exe',['-NoProfile','-Command',command],{windowsHide:true,encoding:'utf8'}))
 if(Number(output.pid)!==proof.pid||Date.parse(output.created_at_utc)!==Date.parse(proof.process_created_at_utc))throw new Error('BLOCK backend process identity drift')
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
 const args=process.argv.slice(2)
 if(args.length===0)console.log(JSON.stringify(dryRun(path.join(root,'release/rc')),null,2))
 else {
  const [mode,approval,hash,...extra]=args
  if(approval!=='--operator-approved'||!['--apply','--rollback'].includes(mode))throw new Error('BLOCK explicit operation/approval/hash required')
  if(mode==='--apply') {
   approvalCheck(true,hash)
   if(extra.length!==1)throw new Error('BLOCK exact backend acceptance receipt required')
   requireBackendReadiness(extra[0])
   console.log(JSON.stringify(await applyRelease({packageDir:path.join(root,'release/rc'),approval:true,expectedManifest:hash,smoke:liveSmoke}),null,2))
  }
  else {
   if(extra.length!==1)throw new Error('BLOCK exact reviewed backup path required')
   console.log(JSON.stringify(rollbackRelease({backup:extra[0],approval:true,expectedManifest:hash}),null,2))
  }
 }
}
