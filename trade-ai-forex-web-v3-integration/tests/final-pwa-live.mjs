/** Isolated browser origins only; real8008 requests remain manual analytic reads. */
import fs from 'node:fs'
import path from 'node:path'
import http from 'node:http'
import net from 'node:net'
import assert from 'node:assert/strict'
import {spawn,spawnSync} from 'node:child_process'
import {chromium} from '@playwright/test'
const root=process.cwd(),out=path.join(root,'release/final-pwa-56cbd7e')
const cacheOnly=process.argv.length===3&&process.argv[2]==='--cache-only'
if(process.argv.length>2&&!cacheOnly)throw new Error('Unsupported test mode')
const free=()=>new Promise(resolve=>{const s=net.createServer();s.listen(0,'127.0.0.1',()=>{const p=s.address().port;s.close(()=>resolve(p))})})
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-extensions']})
let child,server
try{
 if(!cacheOnly){
 const port=await free();assert.ok(![5173,8005,8006,8007,8008].includes(port))
 const config=path.join(root,'.artifacts/final-live-vite.mjs')
 fs.writeFileSync(config,"import {mergeConfig} from 'vite';import base from '../vite.config.ts';export default mergeConfig(base,{server:{watch:{ignored:['**/.artifacts/**','**/release/**','**/test-results/**']}}});\n")
 const log=fs.openSync(path.join(root,'.artifacts/final-pwa-live-server.log'),'w')
 child=spawn(process.execPath,['node_modules/vite/bin/vite.js','--config',config,'--host','127.0.0.1','--port',String(port),'--strictPort'],{cwd:root,windowsHide:true,env:{...process.env,V3_ANALYSIS_PROXY_TARGET:'http://127.0.0.1:8008'},stdio:['ignore',log,log]})
 fs.closeSync(log)
 for(let i=0;i<100;i++){try{if((await fetch('http://127.0.0.1:'+port)).ok)break}catch{};await new Promise(r=>setTimeout(r,100))}
 const context=await browser.newContext({viewport:{width:390,height:844}})
 // Prevent chart/news polling from touching the separate live bridge services.
 await context.route('**/mt5/**',r=>r.fulfill({json:{candles:[],tick:null}}))
 await context.route('**/news/**',r=>r.fulfill({json:{items:[],events:[],data_status:'DATA_UNAVAILABLE'}}))
 const page=await context.newPage();await page.goto('http://127.0.0.1:'+port)
 let count=0;page.on('request',r=>{if(r.url().endsWith('/engine/api/v5/analysis'))count++})
 const results={}
 for(const symbol of ['XAUUSD','EURUSD','GBPUSD','USDJPY']){
  await page.locator('#market-symbol').selectOption(symbol)
  const panel=page.getByRole('region',{name:'Manuel Forex analizi',exact:true})
  await panel.getByLabel('Varsayımsal sermaye (USC)').fill('10000')
  const received=page.waitForResponse(r=>r.url().endsWith('/engine/api/v5/analysis'))
  await panel.getByRole('button',{name:'Analiz Et',exact:true}).click()
  const response=await received;assert.equal(response.status(),200);const data=await response.json()
  assert.equal(data.provider,'mt5');assert.equal(data.symbol,symbol);assert.equal(data.execution_permission,false)
  assert.equal(data.trading_eligibility,'BLOCKED');assert.equal(data.account_currency,'USC')
  assert.equal(data.spread_status.policy_status,'UNAPPROVED');assert.equal(data.spread_status.decision,'BLOCK')
  assert.equal(data.historical_session_evidence.historical_gap_authorized,false)
  await panel.getByTestId('analysis-plan').waitFor();assert.ok((await panel.textContent()).includes('BLOCKED_BY_EXTERNAL_EVIDENCE'))
  assert.ok(!(await panel.getByTestId('analysis-plan').textContent()).includes('Varsayımsal teknik plan — emir izni yok'))
  assert.ok(!(await panel.textContent()).includes('TEST VERİSİ'))
  results[symbol]={final_decision:data.final_decision,plan_hidden:true,account_currency:data.account_currency,provider:data.provider}
 }
 assert.equal(count,4);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth))
 await page.screenshot({path:path.join(root,'.artifacts/final-pwa-real8008-mobile.png')})
 fs.writeFileSync(path.join(out,'real-browser.json'),JSON.stringify({status:'PASS',observed_at:new Date().toISOString(),physical_phone:false,viewport:'390x844',isolated_web_port:port,manual_requests:count,source:'REAL8008_ANALYTIC_READS',results},null,2))
 await context.close()
 }

 // Disposable same-origin legacy-worker -> current production-worker migration.
 let mode='legacy'
 const legacy="self.addEventListener('install',e=>e.waitUntil(caches.open('workbox-precache-v2-'+self.registration.scope).then(c=>c.put('/old-only.js',new Response('OLD FIXTURE SHELL'))).then(()=>self.skipWaiting())));self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));"
 server=http.createServer((req,res)=>{
  const url=new URL(req.url,'http://localhost')
  res.setHeader('Cache-Control','no-store')
  if(url.pathname==='/legacy-sw.js'){res.setHeader('Content-Type','application/javascript');res.end(legacy);return}
  if(mode==='legacy'&&url.pathname==='/'){res.setHeader('Content-Type','text/html');res.end('<!doctype html><title>OLD FIXTURE</title><p>OLD FIXTURE SHELL</p>');return}
  if(/^\/(engine|mt5|news)\//.test(url.pathname)){res.writeHead(503,{'Content-Type':'application/json'});res.end('{"fixture":true}');return}
  const file=path.resolve(root,'dist','.'+(url.pathname==='/'?'/index.html':url.pathname))
  if(!file.startsWith(path.join(root,'dist')+path.sep)||!fs.existsSync(file)){res.writeHead(404);res.end();return}
  const types={'.js':'application/javascript','.css':'text/css','.html':'text/html','.webmanifest':'application/manifest+json','.png':'image/png','.svg':'image/svg+xml'}
  res.setHeader('Content-Type',types[path.extname(file)]??'application/octet-stream');res.end(fs.readFileSync(file))
 })
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin='http://127.0.0.1:'+server.address().port
 const cacheContext=await browser.newContext(),cachePage=await cacheContext.newPage();await cachePage.goto(origin)
 await cachePage.evaluate(async()=>{await navigator.serviceWorker.register('/legacy-sw.js',{scope:'/'});await navigator.serviceWorker.ready})
 await cachePage.waitForFunction(()=>navigator.serviceWorker.controller?.scriptURL.endsWith('/legacy-sw.js'))
 assert.ok((await cachePage.evaluate(async()=>{const result=[];for(const k of await caches.keys())for(const r of await(await caches.open(k)).keys())result.push(r.url);return result})).some(u=>u.endsWith('/old-only.js')))
 mode='current'
 await cachePage.evaluate(async()=>{await navigator.serviceWorker.register('/sw.js',{scope:'/'});await navigator.serviceWorker.ready})
 await cachePage.waitForFunction(()=>navigator.serviceWorker.controller?.scriptURL.endsWith('/sw.js'))
 await cachePage.goto(origin);await cachePage.getByRole('region',{name:'Manuel Forex analizi',exact:true}).waitFor()
 const cached=await cachePage.evaluate(async()=>{const urls=[];for(const k of await caches.keys())for(const r of await(await caches.open(k)).keys())urls.push(r.url);return urls})
 assert.ok(!cached.some(u=>u.endsWith('/old-only.js')));assert.ok(!cached.some(u=>/\/(engine|mt5|news)\//.test(u)))
 const manifest=await (await cachePage.request.get(origin+'/manifest.webmanifest')).json();assert.equal(manifest.display,'standalone');assert.equal(manifest.scope,'/')
 await cacheContext.setOffline(true);await cachePage.reload();await cachePage.getByRole('region',{name:'Manuel Forex analizi',exact:true}).waitFor()
 const offline=await cachePage.evaluate(async()=>{try{await fetch('/engine/offline-probe',{method:'POST',body:'{}'});return false}catch{return true}})
 assert.equal(offline,true)
 fs.writeFileSync(path.join(out,'cache-upgrade.json'),JSON.stringify({status:'PASS',observed_at:new Date().toISOString(),physical_phone:false,fixture_only:true,checks:['legacy_worker_control','current_worker_takeover','old_cache_entry_removed','no_api_cache','manifest_standalone_scope','current_shell_offline','offline_analysis_POST_refused'],cached_urls:cached},null,2))
 await cacheContext.close();console.log(cacheOnly?'PASS disposable SW upgrade/cache 7/7; live8008 NOT_TESTED':'PASS real8008 mobile 4/4; disposable SW upgrade/cache 7/7')
}catch(error){
 fs.writeFileSync(path.join(out,'latest-browser-failure.json'),JSON.stringify({status:'FAIL',observed_at:new Date().toISOString(),mode:cacheOnly?'CACHE_FIXTURE_ONLY':'REAL8008',reason:error.message},null,2))
 throw error
}finally{
 await browser.close();if(server)await new Promise(resolve=>server.close(resolve))
 if(child&&child.exitCode===null)spawnSync('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'})
}
