import fs from 'node:fs'
import path from 'node:path'
import net from 'node:net'
import crypto from 'node:crypto'
import {spawn,spawnSync} from 'node:child_process'
import {chromium,expect} from '@playwright/test'
import {root,sha} from './release-package.mjs'

const out=path.join(root,'.artifacts/cutover'),children=[]
const freePort=()=>new Promise((resolve,reject)=>{const s=net.createServer();s.on('error',reject);s.listen(0,'127.0.0.1',()=>{const port=s.address().port;s.close(()=>resolve(port))})})
const apiPort=await freePort(),webPort=await freePort()
if([apiPort,webPort].some(p=>[5173,8005,8006,8007].includes(p))||apiPort===webPort)throw new Error('BLOCK protected port')
function start(binary,args,name,env=process.env){const log=fs.openSync(path.join(out,name+'.log'),'w');const child=spawn(binary,args,{cwd:root,env,windowsHide:true,stdio:['ignore',log,log]});children.push(child);return child}
async function ready(url,child){for(let i=0;i<150;i++){if(child.exitCode!==null)throw new Error('Owned startup failed');try{if((await fetch(url)).ok)return}catch{}await new Promise(r=>setTimeout(r,200))}throw new Error('Owned startup timeout')}
let browser,failed=false
const results={mode:'ISOLATED_UI_AND_PRODUCTION_READONLY_BACKEND',live_apply:false,apiPort,webPort,symbols:[],analysis_calls:0,order_calls:0}
try {
 const config=path.join(root,'release/reconciled-56cbd7e/runtime-config.json')
 const api=start(path.join(out,'runtime-venv/Scripts/python.exe'),['-B','tools/cutover-runtime.py','--release',path.join(root,'release/reconciled-56cbd7e/backend-56cbd7e'),'--config',config,'--config-sha256',sha(fs.readFileSync(config)),'--manifest',path.join(out,'e2e-runtime-'+crypto.randomUUID()+'.json'),'--port',String(apiPort)],'e2e-api')
 await ready('http://127.0.0.1:'+apiPort+'/api/v1/health',api)
 const vite=start(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',String(webPort),'--strictPort'],'e2e-vite',{...process.env,V3_ANALYSIS_PROXY_TARGET:'http://127.0.0.1:'+apiPort})
 await ready('http://127.0.0.1:'+webPort,vite)
 browser=await chromium.launch({channel:'msedge',headless:true,args:['--disable-extensions']})
 const page=await browser.newPage({viewport:{width:390,height:844}})
 await page.route('**/*',async route=>{
  if(/\/api\/(order|trade|position)/i.test(new URL(route.request().url()).pathname)){results.order_calls++;return route.abort()}
  return route.continue()
 })
 await page.goto('http://127.0.0.1:'+webPort,{waitUntil:'domcontentloaded',timeout:60000})
 for(const symbol of ['XAUUSD','EURUSD','GBPUSD','USDJPY']) {
  await page.locator('#market-symbol').selectOption(symbol)
  const panel=page.getByRole('region',{name:'Manuel Forex analizi',exact:true})
  await panel.getByLabel('Varsayımsal sermaye (USC)').fill('10000')
  const responsePromise=page.waitForResponse(r=>r.url().endsWith('/engine/api/v5/analysis')&&r.request().method()==='POST',{timeout:30000})
  await panel.getByRole('button',{name:'Analiz Et',exact:true}).click()
  const response=await responsePromise,data=await response.json(),body=response.request().postDataJSON();results.analysis_calls++
  expect(response.status()).toBe(200);expect(body.symbol).toBe(symbol);expect(body.hypothetical_currency).toBe('USC');expect(body.balance).toBeUndefined()
  expect(data.execution_permission).toBe(false);expect(data.account_currency).toBe('USC');expect(data.spread_status.policy_status).toBe('UNAPPROVED');expect(data.spread_status.decision).toBe('BLOCK');expect(data.entry_zone).toBeNull();expect(data.lot_size).toBeNull()
  await expect(panel.getByRole('heading',{name:/INSUFFICIENT_DATA/})).toBeVisible({timeout:15000})
  await expect(panel).toContainText('USC')
  await expect(page.getByRole('button',{name:/emir gönder|işlem aç|pozisyon aç|order send/i})).toHaveCount(0)
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  results.symbols.push({symbol,status:response.status(),decision:data.final_decision,execution_permission:data.execution_permission,spread:data.spread_status.policy_status,plan:null})
 }
 expect(results.order_calls).toBe(0);expect(results.analysis_calls).toBe(4)
 await page.getByRole('region',{name:'Manuel Forex analizi',exact:true}).screenshot({path:path.join(out,'real-readonly-ui-mobile.png')})
 results.status='PASS'
}catch(error){failed=true;results.status='FAIL';results.error=error.message}
finally {
 if(browser)await browser.close()
 for(const child of children.reverse())if(child.exitCode===null)spawnSync('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'})
 await new Promise(r=>setTimeout(r,200))
 const closed=[]
 for(const port of [apiPort,webPort])closed.push(await new Promise(resolve=>{const s=net.connect(port,'127.0.0.1');s.once('connect',()=>{s.destroy();resolve(false)});s.once('error',()=>resolve(true))}))
 results.owned_ports_closed=closed.every(Boolean);if(!results.owned_ports_closed){failed=true;results.status='FAIL'}
 fs.writeFileSync(path.join(out,'e2e-results.json'),JSON.stringify(results,null,2))
 console.log(JSON.stringify(results,null,2));process.exitCode=failed?1:0
}
