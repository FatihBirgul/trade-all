import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import {execFileSync} from 'node:child_process'
import {fileURLToPath} from 'node:url'

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
export const original = path.resolve(root, '../trade-ai-forex-web')
export const base = '01c96bb950804ed11fdb512937a81b554ddd669c'
export const payloadPaths = ['src/AnalysisPanel.tsx','src/AnalysisPanel.css','src/analysis/contract.ts','src/analysis/client.ts','src/App.tsx','src/AnalysisNewsRisk.tsx','src/CalendarPanel.tsx','src/MarketChart.tsx','src/RiskCalculator.tsx'].sort()
export const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex')
const git = (...args) => execFileSync('git', args, {cwd:root,stdio:['ignore','pipe','pipe']})
const canonical = b => Buffer.from(b.toString('utf8').replace(/\r\n/g,'\n'))
const optional = p => fs.existsSync(p) ? fs.readFileSync(p) : null
const hash = b => b === null ? null : sha(b)
export function inventory(dir) {
 const result=[]
 const walk=(relative)=>{
  const absolute=path.join(dir,relative)
  if(fs.lstatSync(absolute).isSymbolicLink()) throw new Error('BLOCK symlink: '+relative)
  for(const entry of fs.readdirSync(absolute,{withFileTypes:true})) {
   const p=relative+'/'+entry.name
   if(entry.isSymbolicLink()) throw new Error('BLOCK symlink: '+p)
   if(entry.isDirectory()) walk(p)
   else if(/\.(tsx?|css|svg|png|ico|webp|jpe?g|json)$/.test(p)) result.push(p)
  }
 }
 for(const d of ['src','public']) if(fs.existsSync(path.join(dir,d))) walk(d)
 for(const name of ['package.json','package-lock.json','vite.config.ts','eslint.config.js','tsconfig.json','tsconfig.app.json','tsconfig.node.json','index.html','mt5_bridge.py','news_bridge.py']) if(fs.existsSync(path.join(dir,name))) result.push(name)
 return result.sort()
}
export function buildPackage() {
 const out=path.join(root,'release/rc')
 if(fs.existsSync(out)) throw new Error('Package exists; retain it and use a new release directory after review')
 const tracked=git('ls-files').toString().trim().split(/\r?\n/)
 const baseline=git('ls-tree','-r','--name-only',base).toString().trim().split(/\r?\n/)
 const liveInventory=inventory(original)
 const files=[...new Set([...tracked,...baseline,...payloadPaths,...liveInventory])].filter(file=>!file.startsWith('docs/')).sort()
 const rows=files.map(file=>{
  let b=null;if(baseline.includes(file)) b=git('show',base+':'+file)
  const i=optional(path.join(root,file)), l=optional(path.join(original,file))
  const equals=(a,b)=>a===null||b===null?a===b:sha(canonical(a))===sha(canonical(b))
  const changed=!equals(b,i), drift=!equals(b,l)
  const conflict=changed&&drift&&!equals(i,l)
  return {file,base_sha256:hash(b),isolated_sha256:hash(i),live_sha256:hash(l),canonical_base_sha256:hash(b&&canonical(b)),canonical_isolated_sha256:hash(i&&canonical(i)),canonical_live_sha256:hash(l&&canonical(l)),owner:drift?'LIVE_SOURCE_EXTERNAL_OR_UNKNOWN':changed?'ISOLATED_TASK':'BASE_SNAPSHOT',status:conflict?'CONFLICT_REQUIRES_REVIEW':drift?'LIVE_ONLY_OR_CHANGED':changed?'ISOLATED_ONLY':'UNCHANGED',recommendation:conflict?'BLOCK':payloadPaths.includes(file)?'RUNTIME_PAYLOAD_EXACT_HASH_GUARD':file==='src/NewsPanel.tsx'?'PRESERVE_LIVE_NO_COPY':'EXCLUDE_FROM_RUNTIME_PAYLOAD'}
 })
 const conflicts=rows.filter(r=>payloadPaths.includes(r.file)&&r.status==='CONFLICT_REQUIRES_REVIEW')
 if(conflicts.length) throw new Error('BLOCK conflicts: '+conflicts.map(r=>r.file))
 fs.mkdirSync(path.join(out,'payload'),{recursive:true})
 for(const file of payloadPaths) {const dest=path.join(out,'payload',file);fs.mkdirSync(path.dirname(dest),{recursive:true});fs.copyFileSync(path.join(root,file),dest)}
 const manifest={format:1,mode:'DRY_RUN_ONLY',created_at:new Date().toISOString(),base,snapshot_time:git('show','-s','--format=%cI',base).toString().trim(),source_head:git('rev-parse','HEAD').toString().trim(),target_root:original,files:payloadPaths.map(file=>({file,source_sha256:sha(fs.readFileSync(path.join(root,file))),expected_target_sha256:hash(optional(path.join(original,file)))})),guard_inventory:liveInventory,guards:liveInventory.map(file=>({file,sha256:sha(fs.readFileSync(path.join(original,file)))})),matrix:rows}
 const data=JSON.stringify(manifest,null,2)+'\n'
 fs.writeFileSync(path.join(out,'manifest.json'),data)
 fs.writeFileSync(path.join(out,'manifest.sha256'),sha(data)+'\n')
 fs.mkdirSync(path.join(root,'docs'),{recursive:true})
 fs.writeFileSync(path.join(root,'docs/V3_PWA_ORIGINAL_DIFF_MATRIX.md'),'# Üç yönlü kaynak karşılaştırması\n\nBASE: `'+base+'`; snapshot zamanı: '+manifest.snapshot_time+'. Bu, orijinalin Git geçmişi değildir. Git blob hashleri LF; canlı ve izole hashler gerçek baytlardır. Eşitlik CRLF→LF normalizasyonuyla değerlendirilir. Sahip kişi doğrulanamaz; sınıflandırma değişiklik yönünü gösterir. null/— dosya yok demektir. Otomatik üretilen bu belgenin kendi hash’i manifestte kanıt olarak kullanılmaz.\n\n| Dosya | BASE SHA-256 | ISOLATED SHA-256 | LIVE SHA-256 | Sahip/yön | Durum | Öneri |\n|---|---|---|---|---|---|---|\n'+rows.filter(r=>(r.status!=='UNCHANGED'||['src/MarketChart.tsx','src/NewsPanel.tsx'].includes(r.file))&&!r.file.startsWith('docs/')).map(r=>'| '+r.file+' | '+(r.base_sha256??'—')+' | '+(r.isolated_sha256??'—')+' | '+(r.live_sha256??'—')+' | '+r.owner+' | '+r.status+' | '+r.recommendation+' |').join('\n')+'\n\nBelgeler runtime payload değildir; teslim arşivinde bulunur. Python bridge dosyaları snapshot kapsamı dışında canlı kaynaklardır; korunur, kopyalanmaz.\n')
 return manifest
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {const m=buildPackage();console.log(JSON.stringify({result:'PACKAGED',files:m.files.length,guards:m.guards.length,conflicts:m.matrix.filter(r=>r.status==='CONFLICT_REQUIRES_REVIEW').length}))}
