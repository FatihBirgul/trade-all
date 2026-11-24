import {test} from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import {spawnSync} from 'node:child_process'
import {root,sha,inventory} from '../tools/release-package.mjs'
import {packageDir,dryRun,applyRelease,rollback} from '../tools/final-pwa-promotion.mjs'
function lab(){
 const dir=fs.mkdtempSync(path.join(root,'.artifacts/final-pwa-lab-')),target=path.join(dir,'target'),pkg=path.join(dir,'package')
 fs.mkdirSync(target);fs.mkdirSync(pkg)
 for(const n of ['manifest.json','manifest.sha256'])fs.copyFileSync(path.join(packageDir,n),path.join(pkg,n))
 fs.cpSync(path.join(packageDir,'payload'),path.join(pkg,'payload'),{recursive:true})
 const m=JSON.parse(fs.readFileSync(path.join(pkg,'manifest.json')))
 for(const g of m.guards){const dest=path.join(target,g.file);fs.mkdirSync(path.dirname(dest),{recursive:true});fs.copyFileSync(path.join(packageDir,'destination-backup',g.file),dest)}
 return {dir,target,pkg,m,operatorApproved:true,expectedManifest:sha(fs.readFileSync(path.join(pkg,'manifest.json'))),backupRoot:path.join(dir,'backups'),smoke:async()=>true}
}
const fp=dir=>Object.fromEntries(inventory(dir).map(f=>[f,sha(fs.readFileSync(path.join(dir,f)))]))
test('default new CLI dry-run has zero writes and deletes',()=>{
 const result=spawnSync(process.execPath,['tools/final-pwa-promotion.mjs'],{cwd:root,encoding:'utf8'})
 assert.equal(result.status,0,result.stderr);const d=JSON.parse(result.stdout);assert.equal(d.writes,0);assert.equal(d.deletes,0);assert.equal(d.files,9)
})
test('read-only dry-run retains all fixture bytes',()=>{const c=lab(),before=fp(c.target);assert.equal(dryRun(c.pkg,c.target).writes,0);assert.deepEqual(fp(c.target),before)})
for(const name of ['src/AnalysisPanel.tsx','src/MarketChart.tsx','src/NewsPanel.tsx','vite.config.ts','mt5_bridge.py'])
test('new external edit blocks before backup '+name,async()=>{const c=lab();fs.appendFileSync(path.join(c.target,name),'\nexternal');await assert.rejects(applyRelease(c),/BLOCK target guard drift/);assert.equal(fs.existsSync(c.backupRoot),false)})
test('without separate operator approval nothing is backed up or changed',async()=>{const c=lab();await assert.rejects(applyRelease({...c,operatorApproved:false}),/operator approval/);assert.equal(fs.existsSync(c.backupRoot),false)})
test('wrong approved manifest blocks',async()=>{const c=lab();await assert.rejects(applyRelease({...c,expectedManifest:'0'.repeat(64)}),/exact manifest/)})
test('payload corruption blocks',async()=>{const c=lab();fs.appendFileSync(path.join(c.pkg,'payload/src/AnalysisPanel.tsx'),'\ncorrupt');await assert.rejects(applyRelease(c),/payload hash/)})
test('new target source blocks',()=>{const c=lab();fs.writeFileSync(path.join(c.target,'src/OtherWork.tsx'),'user');assert.throws(()=>dryRun(c.pkg,c.target),/inventory drift/)})
test('fixture apply and rollback preserve chart19, news, bridge, proxy and user bytes',async()=>{
 const c=lab(),before=fp(c.target),order=[]
 const result=await applyRelease({...c,beforeReplace:({file})=>order.push(file)})
 assert.equal(result.status,'APPLIED_SMOKE_PASS');assert.equal(order.at(-1),'src/App.tsx')
 for(const f of c.m.files)assert.equal(sha(fs.readFileSync(path.join(c.target,f.file))),f.source_sha256)
 for(const f of ['src/NewsPanel.tsx','mt5_bridge.py','news_bridge.py','vite.config.ts'])assert.equal(sha(fs.readFileSync(path.join(c.target,f))),before[f])
 assert.equal(rollback({...c,backup:result.backup}).status,'ROLLED_BACK');assert.deepEqual(fp(c.target),before)
 assert.ok(fs.existsSync(path.join(result.backup,'retained-new-files/src/analysis/client.ts')))
})
test('failed smoke restores every original byte',async()=>{const c=lab(),before=fp(c.target);await assert.rejects(applyRelease({...c,smoke:async()=>false}),/ROLLED_BACK/);assert.deepEqual(fp(c.target),before)})
test('partial apply is rolled back',async()=>{const c=lab(),before=fp(c.target);await assert.rejects(applyRelease({...c,beforeReplace:({index})=>{if(index===5)throw new Error('fixture failure')}}),/ROLLED_BACK/);assert.deepEqual(fp(c.target),before)})
test('concurrent edit is retained and stops automatic rollback',async()=>{const c=lab();await assert.rejects(applyRelease({...c,beforeReplace:({index})=>{if(index===3){fs.appendFileSync(path.join(c.target,'src/AnalysisPanel.tsx'),'\nUSER');throw new Error('stop')}}}),/rollback review/);assert.match(fs.readFileSync(path.join(c.target,'src/AnalysisPanel.tsx'),'utf8'),/USER$/)})
test('backup corruption blocks rollback',async()=>{const c=lab(),r=await applyRelease(c);fs.appendFileSync(path.join(r.backup,'before/src/AnalysisPanel.tsx'),'bad');assert.throws(()=>rollback({...c,backup:r.backup}),/corrupt backup/)})
test('CLI cannot APPLY in this read-only task',()=>{const r=spawnSync(process.execPath,['tools/final-pwa-promotion.mjs','--apply'],{cwd:root,encoding:'utf8'});assert.notEqual(r.status,0);assert.match(r.stderr,/DRY_RUN only/)})
