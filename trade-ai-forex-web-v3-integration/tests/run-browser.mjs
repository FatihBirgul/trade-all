import {spawn,spawnSync} from 'node:child_process'
import net from 'node:net'
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'

const root=process.cwd(),out=path.join(root,'.artifacts/browser-runtime');fs.mkdirSync(out,{recursive:true})
const backend=path.resolve(root, '../day-trader-skill')
const py=process.env.TRADE_TEST_PYTHON || 'python'
const freePort=()=>new Promise((resolve,reject)=>{const s=net.createServer();s.on('error',reject);s.listen(0,'127.0.0.1',()=>{const port=s.address().port;s.close(()=>resolve(port))})})
const children=[]
function start(binary,args,name,env){
 const log=fs.openSync(path.join(out,name+'.log'),'w')
 const child=spawn(binary,args,{cwd:root,env,windowsHide:true,stdio:['ignore',log,log]});children.push(child);return child
}
async function ready(url,child){
 for(let i=0;i<150;i++){
  if(child.exitCode!==null)throw new Error('Owned process exited: '+url)
  try {const r=await fetch(url);if(r.ok)return}catch{}
  await new Promise(resolve=>setTimeout(resolve,100))
 }
 throw new Error('Owned startup timeout: '+url)
}
const env={...process.env,PYTHONDONTWRITEBYTECODE:'1'}
// Browser profiles must stay outside Vite's watched source tree. Cookie locks
// and test/backup artifacts otherwise cause reloads during navigation.
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'trade-ai-pwa-qa-'));env.TMP=temp;env.TEMP=temp
const fixtureConfig=path.join(out,'vite-fixture.config.mjs')
fs.writeFileSync(fixtureConfig,`import {mergeConfig} from 'vite';
import base from '../../vite.config.ts';
const target = process.env.V3_ANALYSIS_PROXY_TARGET;
export default mergeConfig(base, {server: {
  proxy: {'/mt5': {target}, '/news': {target}},
  watch: {ignored: ['**/.artifacts/**', '**/test-results/**', '**/release/**']},
  warmup: {clientFiles: ['./src/main.tsx']}
}});
`)
for(const name of Object.keys(env))if(name.startsWith('MT5_')||name.startsWith('V2_'))delete env[name]
env.V3_QA_RUN_NONCE=crypto.randomUUID()
const apiPort=await freePort(),webPort=await freePort()
if([5173,8005,8006,8007,8008].includes(apiPort)||[5173,8005,8006,8007,8008].includes(webPort)||apiPort===webPort)throw new Error('Unsafe port selection')
let failed=false
try{
 const api=start(py,[backend+'/tools/runtime_acceptance/fixture_server.py','--fixture-only',String(apiPort),path.join(out,'manifest.json'),path.resolve(root, '../trade-ai-v2-antigravity')],'api',env)
 await ready('http://127.0.0.1:'+apiPort+'/api/v1/health',api)
 const preview=process.argv.includes('--preview')
 const vite=start(process.execPath,['node_modules/vite/bin/vite.js',...(preview?['preview']:[]),'--config',fixtureConfig,'--host','127.0.0.1','--port',String(webPort),'--strictPort'],'vite',
   {...env,TRADE_TAILSCALE_HOST:'pc.example.ts.net',V3_ANALYSIS_PROXY_TARGET:'http://127.0.0.1:'+apiPort})
 await ready('http://127.0.0.1:'+webPort,vite)
 const extra=process.argv.slice(2).filter(arg=>arg!=='--preview')
 const command=spawn(process.execPath,['node_modules/@playwright/test/cli.js','test',...extra],{cwd:root,windowsHide:true,stdio:'inherit',
   env:{...env,PWA_TEST_URL:'http://127.0.0.1:'+webPort,PWA_TEST_API_PORT:String(apiPort),PWA_TEST_PREVIEW:preview?'1':'0'}})
 const code=await new Promise(resolve=>command.on('exit',resolve));failed=code!==0
 fs.writeFileSync(path.join(out,'processes.json'),JSON.stringify({apiPort,webPort,ownedPids:children.map(p=>p.pid),scope:'FIXTURE_ONLY_NO_TERMINAL'},null,2))
}catch(error){console.error(error);failed=true}
finally{
 for(const child of children.reverse())if(child.exitCode===null){
   if(process.platform==='win32')spawnSync('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'})
   else child.kill()
 }
 await new Promise(resolve=>setTimeout(resolve,250))
 for(const port of [apiPort,webPort]){
  const alive=await new Promise(resolve=>{const s=net.connect(port,'127.0.0.1');s.once('connect',()=>{s.destroy();resolve(true)});s.once('error',()=>resolve(false))})
  if(alive){console.error('Owned port still open:',port);failed=true}
 }
 console.log('Owned fixture API and Vite processes closed; protected service ports never targeted.')
}
process.exitCode=failed?1:0
