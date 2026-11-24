import {test} from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import {spawnSync} from 'node:child_process'
import {root,sha} from '../tools/release-package.mjs'
import {applyRelease,rollbackRelease,rcManifestSha} from '../tools/promotion-apply.mjs'
import {hydrate} from './frozen-target.mjs'

const approved={approval:true,expectedManifest:rcManifestSha}
function lab() {
 const dir=fs.mkdtempSync(path.join(root,'.artifacts/cutover/apply-lab-'))
 const target=path.join(dir,'target'),packageDir=path.join(dir,'package'),backupRoot=path.join(dir,'backups')
 fs.mkdirSync(target);fs.mkdirSync(packageDir)
 for(const name of ['manifest.json','manifest.sha256'])fs.copyFileSync(path.join(root,'release/rc',name),path.join(packageDir,name))
 fs.cpSync(path.join(root,'release/rc/payload'),path.join(packageDir,'payload'),{recursive:true})
 const manifest=JSON.parse(fs.readFileSync(path.join(packageDir,'manifest.json')))
 hydrate(manifest,target)
 return {target,packageDir,backupRoot,manifest,...approved,smoke:async()=>true}
}
const hash=p=>fs.existsSync(p)?sha(fs.readFileSync(p)):null
function before(c) {for(const f of c.manifest.files)assert.equal(hash(path.join(c.target,f.file)),f.expected_target_sha256)}
function after(c) {for(const f of c.manifest.files)assert.equal(hash(path.join(c.target,f.file)),f.source_sha256)}
test('legacy default CLI refuses its stale target baseline',()=>{const r=spawnSync(process.execPath,['tools/promotion-apply.mjs'],{cwd:root,encoding:'utf8'});assert.notEqual(r.status,0);assert.match(r.stderr,/BLOCK target guard drift/)})
test('live APPLY CLI cannot bypass backend acceptance gate',()=>{const r=spawnSync(process.execPath,['tools/promotion-apply.mjs','--apply','--operator-approved',rcManifestSha],{cwd:root,encoding:'utf8'});assert.notEqual(r.status,0);assert.match(r.stderr,/exact backend acceptance receipt required/)})
test('missing operator approval blocks before backup',async()=>{const c=lab();await assert.rejects(applyRelease({...c,approval:false}),/approval required/);assert.equal(fs.existsSync(c.backupRoot),false);before(c)})
test('incorrect approved manifest blocks',async()=>{const c=lab();await assert.rejects(applyRelease({...c,expectedManifest:'0'.repeat(64)}),/exact approved manifest/);before(c)})
test('apply and rollback preserve all original bytes and retain new files',async()=>{const c=lab(),news=hash(path.join(c.target,'src/NewsPanel.tsx'));const result=await applyRelease(c);after(c);assert.equal(result.status,'APPLIED_SMOKE_PASS');assert.equal(hash(path.join(c.target,'src/NewsPanel.tsx')),news);const restored=rollbackRelease({...approved,backup:result.backup});assert.equal(restored.status,'ROLLED_BACK');before(c);assert.ok(fs.existsSync(path.join(result.backup,'retained-new-files/src/analysis/client.ts')))})
test('dependencies arrive before panel and App is replaced last',async()=>{const c=lab(),order=[];const r=await applyRelease({...c,beforeReplace:({file})=>order.push(file)});assert.deepEqual(order.slice(0,3),['src/analysis/contract.ts','src/analysis/client.ts','src/AnalysisPanel.css']);assert.equal(order.at(-1),'src/App.tsx');rollbackRelease({...approved,backup:r.backup});before(c)})
test('backups never collide across apply/restore/reapply',async()=>{const c=lab(),a=await applyRelease(c);rollbackRelease({...approved,backup:a.backup});const b=await applyRelease(c);assert.notEqual(a.backup,b.backup);assert.ok(fs.existsSync(path.join(a.backup,'receipt.json')));rollbackRelease({...approved,backup:b.backup});before(c)})
test('target chart/news drift blocks before any write',async()=>{for(const file of ['src/MarketChart.tsx','src/NewsPanel.tsx']){const c=lab();fs.appendFileSync(path.join(c.target,file),'\nuser');await assert.rejects(applyRelease(c),/BLOCK target guard drift/);assert.equal(fs.existsSync(c.backupRoot),false)}})
test('corrupt payload blocks before backup',async()=>{const c=lab();fs.appendFileSync(path.join(c.packageDir,'payload/src/App.tsx'),'user');await assert.rejects(applyRelease(c),/BLOCK payload hash/);before(c)})
test('failed smoke automatically restores all original hashes',async()=>{const c=lab();await assert.rejects(applyRelease({...c,smoke:async()=>false}),/ROLLED_BACK/);before(c)})
test('failure in middle of replacement safely restores partial apply',async()=>{const c=lab();await assert.rejects(applyRelease({...c,beforeReplace:({index})=>{if(index===4)throw new Error('simulated IO failure')}}),/ROLLED_BACK/);before(c)})
test('concurrent user edit prevents unsafe automatic rollback',async()=>{const c=lab();await assert.rejects(applyRelease({...c,beforeReplace:({index})=>{if(index===3){fs.appendFileSync(path.join(c.target,'src/AnalysisPanel.tsx'),'\nuser');throw new Error('stop')}}}),/rollback review required/);assert.match(fs.readFileSync(path.join(c.target,'src/AnalysisPanel.tsx'),'utf8'),/user$/)})
test('rollback refuses post-apply user changes',async()=>{const c=lab(),a=await applyRelease(c);fs.appendFileSync(path.join(c.target,'src/App.tsx'),'\nuser');assert.throws(()=>rollbackRelease({...approved,backup:a.backup}),/rollback review required/);assert.match(fs.readFileSync(path.join(c.target,'src/App.tsx'),'utf8'),/user$/)})
test('corrupt backup blocks restore without altering target',async()=>{const c=lab(),a=await applyRelease(c);fs.appendFileSync(path.join(a.backup,'before/src/App.tsx'),'bad');assert.throws(()=>rollbackRelease({...approved,backup:a.backup}),/backup corruption/);after(c)})
test('receipt corruption blocks restore',async()=>{const c=lab(),a=await applyRelease(c);fs.appendFileSync(path.join(a.backup,'receipt.json'),' ');assert.throws(()=>rollbackRelease({...approved,backup:a.backup}),/receipt integrity/);after(c)})
test('backup inside watched target is rejected',async()=>{const c=lab();await assert.rejects(applyRelease({...c,backupRoot:path.join(c.target,'backups')}),/backup location/);before(c)})
test('unexpected new file blocks restore',async()=>{const c=lab(),a=await applyRelease(c);fs.writeFileSync(path.join(c.target,'src/OtherWork.tsx'),'user');assert.throws(()=>rollbackRelease({...approved,backup:a.backup}),/inventory drift/);after(c)})
test('junction target blocks writes',async()=>{const c=lab();fs.renameSync(path.join(c.target,'src'),path.join(c.target,'saved'));fs.symlinkSync(path.join(c.target,'saved'),path.join(c.target,'src'),'junction');await assert.rejects(applyRelease(c),/BLOCK symlink/);assert.equal(fs.existsSync(c.backupRoot),false)})
