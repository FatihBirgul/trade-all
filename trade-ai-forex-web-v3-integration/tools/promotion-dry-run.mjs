import fs from 'node:fs'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
import {root,original,payloadPaths,sha,inventory} from './release-package.mjs'

function safe(rootDir,relative) {
 if(!relative || relative.includes('\\') || relative.split('/').some(p=>p==='..'||p==='.'||!p) || path.isAbsolute(relative)) throw new Error('BLOCK unsafe path')
 const destination=path.resolve(rootDir,relative)
 for(let current=destination;;current=path.dirname(current)) {
  if(fs.existsSync(current)&&fs.lstatSync(current).isSymbolicLink()) throw new Error('BLOCK symlink')
  if(current===path.dirname(current)) break
 }
 return destination
}
export function dryRun(packageDir,targetDir=original) {
 const data=fs.readFileSync(path.join(packageDir,'manifest.json'))
 if(sha(data)!==fs.readFileSync(path.join(packageDir,'manifest.sha256'),'utf8').trim()) throw new Error('BLOCK manifest hash')
 const m=JSON.parse(data)
 if(m.mode!=='DRY_RUN_ONLY'||m.format!==1||m.target_root!==original) throw new Error('BLOCK package identity')
 if(JSON.stringify(m.files.map(f=>f.file).sort())!==JSON.stringify(payloadPaths)) throw new Error('BLOCK payload allowlist')
 if(JSON.stringify(inventory(targetDir))!==JSON.stringify(m.guard_inventory)) throw new Error('BLOCK target inventory drift')
 if(JSON.stringify(m.guards.map(f=>f.file).sort())!==JSON.stringify(m.guard_inventory)) throw new Error('BLOCK guard coverage')
 for(const f of m.guards) if(sha(fs.readFileSync(safe(targetDir,f.file)))!==f.sha256) throw new Error('BLOCK target guard drift: '+f.file)
 for(const f of m.files) {
  if(sha(fs.readFileSync(safe(path.join(packageDir,'payload'),f.file)))!==f.source_sha256) throw new Error('BLOCK payload hash: '+f.file)
  const target=safe(targetDir,f.file)
  const actual=fs.existsSync(target)?sha(fs.readFileSync(target)):null
  if(actual!==f.expected_target_sha256) throw new Error('BLOCK target hash: '+f.file)
 }
 return {mode:'DRY_RUN_ONLY',status:'READY_FOR_SEPARATE_OPERATOR_APPROVAL',writes:0,deletes:0,files:m.files.length,guards:m.guards.length,manifest_sha256:sha(data),warning:'No APPLY implementation. Live promotion and HMR require a separately approved operation and a fresh preflight.'}
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
 if(process.argv.slice(2).length) throw new Error('BLOCK: arguments/APPLY unsupported; read-only helper')
 console.log(JSON.stringify(dryRun(path.join(root,'release/rc')),null,2))
}
