import fs from 'node:fs'
import path from 'node:path'
import {execFileSync,spawnSync} from 'node:child_process'
import {root,original,base,payloadPaths,sha,inventory} from './release-package.mjs'
import {packageDir,dryRun} from './final-pwa-promotion.mjs'
const git=(...args)=>execFileSync('git',args,{cwd:root})
const blocked=process.argv.length===3&&process.argv[2]==='--blocked-evidence'
if(process.argv.length>2&&!blocked)throw new Error('Unsupported staging argument')
execFileSync(path.join(root,'.artifacts/cutover/runtime-venv/Scripts/python.exe'),['-B','tools/final-pwa-release.py',blocked?'source-guard':'guard'],{cwd:root,windowsHide:true,stdio:'inherit'})
if(fs.existsSync(path.join(packageDir,'sealed.json')))throw new Error('BLOCK sealed release is immutable; create a different release')
const baseline=git('ls-tree','-r','--name-only',base).toString().trim().split(/\r?\n/)
const optional=p=>fs.existsSync(p)?fs.readFileSync(p):null
const hash=x=>x===null?null:sha(x)
const canon=x=>x===null?null:x.toString('utf8').replace(/^\uFEFF/,'').replace(/\r\n/g,'\n')
const guards=inventory(original).map(file=>({file,sha256:hash(optional(path.join(original,file)))}))
const before=JSON.parse(fs.readFileSync(path.join(packageDir,'begin.json')))
const runtime=JSON.parse(fs.readFileSync(path.join(root,'release/approved-8008-62c78b12170f4c8a88896846f4ff152f/result.json')))
const decisions={
 'src/AnalysisPanel.tsx':'MERGED: current distinct refusal states, exact historical-gap explanation, REAL readonly badge and hypothetical USC; RC four-symbol/manual/cancel/timeout/race/pattern/source gates retained',
 'src/App.tsx':'MERGED: preserve all19 current chart options and add RC chartSource prop; no V5 scope expansion',
 'src/MarketChart.tsx':'MERGED: preserve current all-JPY decimal fix; retain RC lazy clock lint fix',
 'src/NewsPanel.tsx':'PRESERVE CURRENT BYTE-FOR-BYTE; excluded from payload',
 'src/RiskCalculator.tsx':'RC context invalidation/draft preservation; new15 chart symbols explicitly excluded from existing four-symbol risk scope',
 'src/AnalysisNewsRisk.tsx':'RC lazy clock initialization; current news behavior preserved',
 'src/CalendarPanel.tsx':'RC lazy clock initialization; current calendar behavior preserved',
 'vite.config.ts':'ISOLATED DEFAULT8008; current proxy byte-preserved, excluded from payload',
 'package.json':'Runtime dependencies unchanged; isolated Playwright dev tooling excluded from live payload',
 'package-lock.json':'No target dependency installation or lockfile replacement',
}
const matrix=[...new Set([...inventory(root),...guards.map(f=>f.file),...payloadPaths])].sort().map(file=>{
 const b=baseline.includes(file)?git('show',base+':'+file):null,c=optional(path.join(original,file)),r=optional(path.join(root,file))
 return {file,base_sha256:hash(b),current_sha256:hash(c),rc_sha256:hash(r),
  current_changed:canon(b)!==canon(c),rc_changed:canon(b)!==canon(r),
  categories:file==='src/AnalysisPanel.tsx'?['Yeni özellik','Kullanıcı tercihi','Bug fix','API uyumu','Haber entegrasyonu','Grafik entegrasyonu','Risk/USC','Styling','Güvenlik']
   :file==='src/MarketChart.tsx'||file==='src/App.tsx'?['Grafik entegrasyonu','Kullanıcı tercihi','Bug fix']:['Güvenlik','Mevcut davranışın korunması'],
  resolution:decisions[file]??(payloadPaths.includes(file)?'RC addition / reviewed safety behavior':'PRESERVE CURRENT; excluded from payload')}
})
const write=(file,data)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,data)}
const json=(file,data)=>write(file,JSON.stringify(data,null,2)+'\n')
for(const g of guards){
 const dest=path.join(packageDir,'destination-backup',g.file)
 if(fs.existsSync(dest)){if(sha(fs.readFileSync(dest))!==g.sha256)throw new Error('BLOCK backup mismatch')}
 else write(dest,fs.readFileSync(path.join(original,g.file)))
 if(sha(fs.readFileSync(dest))!==g.sha256)throw new Error('BLOCK backup verification')
}
const files=payloadPaths.map(file=>{
 const bytes=fs.readFileSync(path.join(root,file));write(path.join(packageDir,'payload',file),bytes)
 const current=optional(path.join(original,file))
 const empty=path.join(packageDir,'diffs/empty-base');if(!fs.existsSync(empty))write(empty,'')
 const diff=spawnSync('git',['diff','--no-index','--no-ext-diff','--',current===null?empty:path.join(original,file),path.join(root,file)],{cwd:root,encoding:'utf8',windowsHide:true})
 if(![0,1].includes(diff.status))throw new Error('BLOCK diff generation: '+file)
 return {file,source_sha256:sha(bytes),expected_target_sha256:hash(current),patch:diff.stdout}
})
// New destinations are diffed against an explicit empty file without touching original.
for(const f of files){write(path.join(packageDir,'diffs',f.file+'.diff'),f.patch);delete f.patch}
json(path.join(packageDir,'conflict-matrix.json'),{base,original_is_git_repository:false,merge_mode:'MANUAL_REVIEWED_THREE_WAY; NO_AUTO_MERGE',decisions:matrix})
json(path.join(packageDir,'source-manifest.json'),{files:files.map(({file,source_sha256})=>({file,sha256:source_sha256}))})
json(path.join(packageDir,'destination-manifest.json'),{target_root:original,guards})
const currentPackage=JSON.parse(fs.readFileSync(path.join(original,'package.json'))),rcPackage=JSON.parse(fs.readFileSync(path.join(root,'package.json')))
if(JSON.stringify(currentPackage.dependencies)!==JSON.stringify(rcPackage.dependencies))throw new Error('BLOCK runtime dependency conflict')
const m={format:2,mode:'DRY_RUN_DEFAULT',deployment_readiness:blocked?'BLOCKED':'STAGED_PENDING_QUALITY_GATES',
 source_head:git('rev-parse','HEAD').toString().trim(),base,target_root:original,files,guard_inventory:guards.map(g=>g.file),guards,
 backend_sha:before.backend_sha,backend_loaded_fingerprint:before.loaded_fingerprint,
 backend_process:before.processes['8008'],backend_startup:runtime.acceptance.startup,
 backend_live_identity_verified:!blocked,blocking_reason:blocked?'8008_UNAVAILABLE_AND_PROTECTED_SERVICE_PID_CHANGES':null,
 proxy:'http://127.0.0.1:8008',pwa_apply_authorized:false,approval_received:false,
 dependency_changes:{runtime:'NONE',target_package_and_lock:'PRESERVED',isolated_dev_dependencies:rcPackage.devDependencies},
 backup_validation:{status:'PASS',scope:'all destination runtime/config guards',files:guards.length,root:'destination-backup'},
 blocker_states:{spread:'UNAPPROVED/BLOCK',historical:'BLOCKED_BY_EXTERNAL_EVIDENCE',execution_permission:false},
 tests:{status:'PENDING'},created_at:new Date().toISOString()}
const data=JSON.stringify(m,null,2)+'\n';write(path.join(packageDir,'manifest.json'),data);write(path.join(packageDir,'manifest.sha256'),sha(data))
console.log(JSON.stringify(dryRun(),null,2))
