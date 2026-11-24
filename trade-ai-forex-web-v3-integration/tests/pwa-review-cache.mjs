/** Disposable fixture origin only. Never requests any protected service. */
import fs from 'node:fs'
import path from 'node:path'
import http from 'node:http'
import assert from 'node:assert/strict'
import {chromium} from '@playwright/test'
const root=process.cwd()
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-extensions']})
let server
try{
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
 fs.writeFileSync(path.join(root,'.artifacts/final-review-cache.json'),JSON.stringify({status:'PASS',observed_at:new Date().toISOString(),physical_phone:false,fixture_only:true,checks:['legacy_worker_control','current_worker_takeover','old_cache_entry_removed','no_api_cache','manifest_standalone_scope','current_shell_offline','offline_analysis_POST_refused'],cached_urls:cached},null,2))
 await cacheContext.close();console.log('PASS disposable SW upgrade/cache 7/7; live8008 NOT_TESTED')
}catch(error){
 fs.writeFileSync(path.join(root,'.artifacts/final-review-cache-failure.json'),JSON.stringify({status:'FAIL',observed_at:new Date().toISOString(),mode:'CACHE_FIXTURE_ONLY',reason:error.message},null,2))
 throw error
}finally{await browser.close();if(server)await new Promise(resolve=>server.close(resolve))}
