/** Recover exact legacy fixture bytes by expected SHA; never substitutes current drift. */
import fs from 'node:fs'
import path from 'node:path'
import {execFileSync} from 'node:child_process'
import {root,sha} from '../tools/release-package.mjs'
export function hydrate(manifest,target){
 for(const g of manifest.guards){
  const candidates=[]
  for(const dir of ['release/runtime8008-56cbd7e/backup','release/reconciled-56cbd7e/preapproval-backup',manifest.target_root]){
   const file=path.join(path.isAbsolute(dir)?dir:path.join(root,dir),g.file)
   if(fs.existsSync(file))candidates.push(fs.readFileSync(file))
  }
  try{
   const bytes=execFileSync('git',['show',manifest.base+':'+g.file],{cwd:root,stdio:['ignore','pipe','ignore']})
   candidates.push(bytes,Buffer.from(bytes.toString().replace(/\r?\n/g,'\r\n')))
  }catch{/* Non-Git original bridge files are backed up separately. */}
  const found=candidates.find(bytes=>sha(bytes)===g.sha256)
  if(!found)throw new Error('Exact legacy fixture bytes unavailable: '+g.file)
  const dest=path.join(target,g.file);fs.mkdirSync(path.dirname(dest),{recursive:true});fs.writeFileSync(dest,found)
 }
}
