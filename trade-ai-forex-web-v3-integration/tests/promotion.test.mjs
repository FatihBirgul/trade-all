import {test} from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import {spawnSync} from 'node:child_process'
import {root,sha} from '../tools/release-package.mjs'
import {dryRun} from '../tools/promotion-dry-run.mjs'
import {hydrate} from './frozen-target.mjs'

const source=path.join(root,'release/rc')
function lab() {
 const dir=fs.mkdtempSync(path.join(root,'.artifacts/promotion-lab-'))
 const target=path.join(dir,'target'),pkg=path.join(dir,'package')
 fs.mkdirSync(target)
 fs.cpSync(source,pkg,{recursive:true})
 const manifest=JSON.parse(fs.readFileSync(path.join(pkg,'manifest.json')))
 hydrate(manifest,target)
 return {dir,target,pkg,manifest}
}
function reseal(c) {const data=JSON.stringify(c.manifest);fs.writeFileSync(path.join(c.pkg,'manifest.json'),data);fs.writeFileSync(path.join(c.pkg,'manifest.sha256'),sha(data))}
function fingerprint(dir) {const out={};function walk(p){for(const e of fs.readdirSync(p,{withFileTypes:true})){const full=path.join(p,e.name);if(e.isDirectory())walk(full);else out[path.relative(dir,full)]=sha(fs.readFileSync(full))}}walk(dir);return out}
test('dry-run validates source and target without any write',()=>{const c=lab(),before=fingerprint(c.dir);assert.equal(dryRun(c.pkg,c.target).writes,0);assert.deepEqual(fingerprint(c.dir),before)})
for(const file of ['src/MarketChart.tsx','src/NewsPanel.tsx','vite.config.ts']) test('blocks external drift in '+file,()=>{const c=lab();fs.appendFileSync(path.join(c.target,file),'\n// external change');assert.throws(()=>dryRun(c.pkg,c.target),/BLOCK target guard drift/)})
test('blocks payload corruption',()=>{const c=lab();fs.appendFileSync(path.join(c.pkg,'payload/src/App.tsx'),'x');assert.throws(()=>dryRun(c.pkg,c.target),/BLOCK payload hash/)})
test('blocks unsealed manifest edits',()=>{const c=lab();fs.appendFileSync(path.join(c.pkg,'manifest.json'),' ');assert.throws(()=>dryRun(c.pkg,c.target),/BLOCK manifest hash/)})
test('blocks traversal and secrets even in a resealed manifest',()=>{for(const name of ['../outside','.env','node_modules/a.js']){const c=lab();c.manifest.files[0].file=name;reseal(c);assert.throws(()=>dryRun(c.pkg,c.target),/BLOCK payload allowlist/)}})
test('blocks newly added target source',()=>{const c=lab();fs.writeFileSync(path.join(c.target,'src/NewOwnerWork.tsx'),'export {}');assert.throws(()=>dryRun(c.pkg,c.target),/BLOCK target inventory drift/)})
test('blocks newly created destination for a new RC file',()=>{const c=lab();fs.mkdirSync(path.join(c.target,'src/analysis'),{recursive:true});fs.writeFileSync(path.join(c.target,'src/analysis/client.ts'),'new owner');assert.throws(()=>dryRun(c.pkg,c.target),/BLOCK target inventory drift/)})
test('CLI refuses APPLY before inspecting target',()=>{const r=spawnSync(process.execPath,['tools/promotion-dry-run.mjs','--apply'],{cwd:root,encoding:'utf8'});assert.notEqual(r.status,0);assert.match(r.stderr,/APPLY unsupported/)})
test('blocks incomplete guard coverage',()=>{const c=lab();c.manifest.guards.pop();reseal(c);assert.throws(()=>dryRun(c.pkg,c.target),/BLOCK guard coverage/)})
test('blocks directory junction instead of target source',()=>{const c=lab();fs.renameSync(path.join(c.target,'src'),path.join(c.target,'saved-source'));fs.symlinkSync(path.join(c.target,'saved-source'),path.join(c.target,'src'),'junction');assert.throws(()=>dryRun(c.pkg,c.target),/BLOCK symlink/)})
