import {test,expect} from '@playwright/test'
import {response} from '../fixtures.mjs'

async function background(page){
 await page.route('**/news/**',route=>route.fulfill({json:{items:[],events:[],data_status:'DATA_UNAVAILABLE'}}))
 await page.route('**/mt5/**',route=>{
  const url=new URL(route.request().url()),now=Math.floor(Date.now()/1000),duration=300
  const candles=Array.from({length:200},(_,i)=>({time:Math.floor(now/duration)*duration-(200-i)*duration,open:1999,high:2001,low:1998,close:2000}))
  return route.fulfill({json:{candles,digits:3,point:.001,captured_at_utc:now,tick:{bid:2000,ask:2000.2,time:now}}})
 })
}
async function open(page){await background(page);await page.goto('/');return page.getByRole('region',{name:'Manuel Forex analizi',exact:true})}
async function fill(panel){await panel.getByLabel('Varsayımsal sermaye (USC)').fill('10000')}
async function mock(page,changes={},status=200){
 await page.route('**/engine/api/v5/analysis',async route=>{
  const input=route.request().postDataJSON()
  const data=response({symbol:input.symbol,timeframe:input.timeframe,...changes})
  await route.fulfill({status,json:status===200?data:{detail:{status:'DATA_UNAVAILABLE',reason:'private-secret-path'}}})
 })
}

test('legacy risk drafts survive symbol changes and stale result is cleared',async({page})=>{
 await open(page)
 await page.route('**/mt5/api/risk-preview?**',route=>route.fulfill({json:{symbol:'XAUUSD',direction:'SELL',demo_only:true,order_sent:false,account_currency:'USC',risk_budget:123.45,volume_min:.01,volume_max:100,volume_step:.01,min_lot_estimated_loss:1,suggested_lot:.1,estimated_loss_at_sl:100,status:'ok',warning:''}}))
 const risk=page.locator('.risk-calculator')
 await risk.locator('#risk-balance').fill('12345')
 await risk.locator('#risk-entry').fill('2000')
 await risk.locator('#risk-stop').fill('2010')
 await risk.locator('#risk-direction').selectOption('SELL')
 await risk.getByRole('button',{name:'Demo Riskini Hesapla'}).click()
 await expect(risk.locator('.risk-result')).toBeVisible()
 await page.locator('#market-symbol').selectOption('EURUSD')
 await expect(risk.locator('.risk-result')).toHaveCount(0)
 await expect(risk.locator('#risk-balance')).toHaveValue('12345')
 await expect(risk.locator('#risk-entry')).toHaveValue('2000')
 await expect(risk.locator('#risk-stop')).toHaveValue('2010')
 await expect(risk.locator('#risk-direction')).toHaveValue('SELL')
 await expect(risk).toContainText('EURUSD')
})
test('four symbols send only manual hypothetical USC requests',async({page})=>{
 let calls=0
 await page.route('**/engine/api/v5/analysis',async route=>{
  calls++;const input=route.request().postDataJSON()
  expect(input.hypothetical_currency).toBe('USC');expect(input.hypothetical_capital).toBe(10000);expect(input.balance).toBeUndefined()
  await route.fulfill({json:response({symbol:input.symbol,timeframe:input.timeframe})})
 })
 let panel=await open(page);await page.waitForTimeout(600);expect(calls).toBe(0)
 for(const symbol of ['XAUUSD','EURUSD','GBPUSD','USDJPY']){
  await page.locator('#market-symbol').selectOption(symbol);panel=page.getByRole('region',{name:'Manuel Forex analizi',exact:true})
  await fill(panel);await panel.getByRole('button',{name:'Analiz Et',exact:true}).click()
  await expect(panel.getByRole('heading',{name:'BUY · teknik aday',exact:true})).toBeVisible()
 }
 expect(calls).toBe(4);await page.waitForTimeout(800);expect(calls).toBe(4)
})
for(const [name,changes,text] of [
 ['BUY',{},'BUY · teknik aday'],['SELL',{final_decision:'SELL_CANDIDATE',legacy_signal:'SELL',stop_loss:2010,take_profit_1:1980,take_profit_2:1970},'SELL · teknik aday'],
 ['WAIT',{final_decision:'WAIT'},'WAIT · bekle'],['NO_TRADE',{final_decision:'NO_TRADE'},'NO_TRADE · plan reddedildi'],
 ['INSUFFICIENT_DATA',{final_decision:'INSUFFICIENT_DATA',data_status:'DATA_UNAVAILABLE',decision_reasons:['missing candle without verified broker hours']},'INSUFFICIENT_DATA · veri yetersiz'],
 ['MARKET_CLOSED',{final_decision:'MARKET_CLOSED',market_status:'CLOSED'},'MARKET_CLOSED · piyasa kapalı'],
 ['PROVIDER_UNAVAILABLE',{final_decision:'PROVIDER_UNAVAILABLE'},'PROVIDER_UNAVAILABLE · kaynak kullanılamıyor'],
 ])test(name+' is distinct',async({page})=>{
 await mock(page,changes);const panel=await open(page);await fill(panel);await panel.getByRole('button',{name:'Analiz Et',exact:true}).click()
 await expect(panel.getByRole('heading',{name:text,exact:true})).toBeVisible()
 if(name==='SELL')await expect(panel.getByTestId('analysis-plan')).toContainText('Varsayımsal teknik plan — emir izni yok')
})
for(const [name,changes] of Object.entries({
 'spread unapproved':{spread_status:{decision:'BLOCK',policy_status:'UNAPPROVED',max_allowed_price:null,reasons:['spread policy operator approval unavailable']}},
 'broker session blocked':{market_status:'UNKNOWN'},'contract unverified':{broker_contract:{status:'UNVERIFIED'}},
 'null lot':{lot_size:null},'currency mismatch':{account_currency:'USD'},'execution permission true':{execution_permission:true},
 'old schema':{broker_contract:undefined,spread_status:undefined},'stale quote':{data_status:'STALE',final_decision:'STALE_DATA'},
 'DATA_UNAVAILABLE':{data_status:'DATA_UNAVAILABLE'},
}))test('safe plan refusal: '+name,async({page})=>{
 await mock(page,changes);const panel=await open(page);await fill(panel);await panel.getByRole('button',{name:'Analiz Et',exact:true}).click()
 await expect(panel.getByTestId('analysis-plan')).toBeVisible()
 await expect(panel.getByTestId('analysis-plan')).not.toContainText('2.000,000')
 await expect(panel.getByTestId('analysis-plan')).not.toContainText('Varsayımsal teknik plan — emir izni yok')
 if(name==='spread unapproved')await expect(panel.getByText('Maksimum spread limiti henüz onaylanmadı. Gözlenen spread izin limiti değildir.')).toBeVisible()
 if(name==='old schema')await expect(panel.getByText(/Backend sürüm\/yapılandırma uyumu doğrulanmadı/)).toBeVisible()
})
test('NOT_EVALUATED stays explicitly hypothetical when all gates pass',async({page})=>{
 await mock(page);const panel=await open(page);await fill(panel);await panel.getByRole('button',{name:'Analiz Et',exact:true}).click()
 await expect(panel.getByTestId('analysis-plan')).toContainText('Varsayımsal teknik plan — emir izni yok')
 await expect(panel.getByTestId('analysis-plan')).toContainText('2.000,000')
 await expect(panel.getByTestId('analysis-plan')).toContainText('NOT_EVALUATED bir emir onayı değildir')
})
for(const pattern of ['Double Top','Double Bottom'])test('descriptive '+pattern,async({page})=>{
 const data=response();data.chart_patterns.items[0].name=pattern
 await mock(page,{chart_patterns:data.chart_patterns});const panel=await open(page);await fill(panel);await panel.getByRole('button',{name:'Analiz Et',exact:true}).click()
 await expect(panel.getByText(pattern,{exact:true})).toBeVisible();await expect(panel.getByText('Doji',{exact:true})).toBeVisible()
 await expect(panel.getByText('DESCRIPTIVE_ONLY',{exact:true})).toHaveCount(2)
})
test('empty patterns do not fabricate a formation',async({page})=>{
 await mock(page,{chart_patterns:{status:'AVAILABLE',role:'DESCRIPTIVE_ONLY',items:[]}})
 const panel=await open(page);await fill(panel);await panel.getByRole('button',{name:'Analiz Et',exact:true}).click()
 await expect(panel.getByText('Bu snapshot içinde formasyon bulunmadı.')).toBeVisible()
})
test('pattern source mismatch is unavailable',async({page})=>{
 const data=response();data.chart_patterns.items[0].source_sha256='c'.repeat(64)
 await mock(page,{chart_patterns:data.chart_patterns});const panel=await open(page);await fill(panel);await panel.getByRole('button',{name:'Analiz Et',exact:true}).click()
 await expect(panel.getByText(/Formasyon kaynak kimliği uyuşmuyor/)).toBeVisible();await expect(panel.getByText('Double Top',{exact:true})).toHaveCount(0)
})
test('missing capital does not send a request',async({page})=>{
 let calls=0;await page.route('**/engine/api/v5/analysis',()=>{calls++})
 const panel=await open(page);await panel.getByRole('button',{name:'Analiz Et',exact:true}).click()
 await expect(panel.getByRole('alert')).toContainText('USC');expect(calls).toBe(0)
})
test('503 response is sanitized',async({page})=>{
 await mock(page,{},503);const panel=await open(page);await fill(panel);await panel.getByRole('button',{name:'Analiz Et',exact:true}).click()
 await expect(panel.getByRole('alert')).toContainText('503');await expect(panel).not.toContainText('private-secret-path')
})
test('network disconnect refuses analysis',async({page})=>{
 await page.route('**/engine/api/v5/analysis',r=>r.abort('internetdisconnected'))
 const panel=await open(page);await fill(panel);await panel.getByRole('button',{name:'Analiz Et',exact:true}).click()
 await expect(panel.getByRole('alert')).toContainText('bağlanılamadı')
})
test('late old-symbol response never appears after selection change',async({page})=>{
 await page.route('**/engine/api/v5/analysis',async route=>{await new Promise(r=>setTimeout(r,350));await route.fulfill({json:response()}).catch(()=>{})})
 let panel=await open(page);await fill(panel);await panel.getByRole('button',{name:'Analiz Et',exact:true}).click()
 await page.locator('#market-symbol').selectOption('EURUSD');panel=page.getByRole('region',{name:'Manuel Forex analizi',exact:true})
 await page.waitForTimeout(500);await expect(panel.getByRole('heading',{name:'Analiz bekleniyor'})).toBeVisible();await expect(panel.getByTestId('analysis-plan')).toHaveCount(0)
})
test('double click sends one request',async({page})=>{
 let calls=0;await page.route('**/engine/api/v5/analysis',async route=>{calls++;await new Promise(r=>setTimeout(r,150));await route.fulfill({json:response()})})
 const panel=await open(page);await fill(panel);await panel.getByRole('button',{name:'Analiz Et',exact:true}).dblclick({force:true})
 await expect(panel.getByRole('heading',{name:'BUY · teknik aday',exact:true})).toBeVisible();expect(calls).toBe(1)
})
test('response identity mismatch never renders plan',async({page})=>{
 await mock(page,{symbol:'USDJPY'});const panel=await open(page);await fill(panel);await panel.getByRole('button',{name:'Analiz Et',exact:true}).click()
 await expect(panel.getByRole('alert')).toContainText('kimliği uyuşmuyor')
})
test('timeout is visible and no automatic retry occurs',async({page})=>{
 await page.clock.install();let calls=0;await page.route('**/engine/api/v5/analysis',()=>{calls++})
 const panel=await open(page);await fill(panel);await panel.getByRole('button',{name:'Analiz Et',exact:true}).click()
 await page.clock.runFor(21000);await expect(panel.getByRole('alert')).toContainText('zaman aşımı');expect(calls).toBe(1)
})
test('result expires locally without background analysis',async({page})=>{
 await page.clock.install();let calls=0
 await page.route('**/engine/api/v5/analysis',r=>{calls++;return r.fulfill({json:response()})})
 const panel=await open(page);await fill(panel);await panel.getByRole('button',{name:'Analiz Et',exact:true}).click()
 await expect(panel.getByTestId('analysis-plan')).toContainText('Varsayımsal teknik plan — emir izni yok')
 await page.clock.runFor(121000);await expect(panel.getByRole('alert')).toContainText('Snapshot güncel değil');expect(calls).toBe(1)
})
test('mobile viewport and no order controls',async({page})=>{
 await page.setViewportSize({width:390,height:844});await mock(page);const panel=await open(page);await fill(panel)
 await panel.getByRole('button',{name:'Analiz Et',exact:true}).click();await expect(panel.getByTestId('analysis-plan')).toBeVisible()
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)
 await expect(page.getByRole('button',{name:/işlem aç|emir gönder|pozisyon aç|order send/i})).toHaveCount(0)
 await panel.screenshot({path:'.artifacts/manual-analysis-mobile.png'})
 if(process.env.PWA_TEST_PREVIEW==='1') {
  const manifest=await (await page.request.get('/manifest.webmanifest')).json()
  expect(manifest.display).toBe('standalone');expect(manifest.scope).toBe('/')
  await page.evaluate(async()=>{await navigator.serviceWorker.ready})
  await expect.poll(()=>page.evaluate(()=>Boolean(navigator.serviceWorker.controller))).toBe(true)
  const cachedUrls=await page.evaluate(async()=>{
   const urls=[];for(const name of await caches.keys())for(const request of await (await caches.open(name)).keys())urls.push(request.url)
   return urls
  })
  expect(cachedUrls.some(url=>/\/(engine|mt5|news)\//.test(url))).toBe(false)
  await page.context().setOffline(true)
  const outcome=await page.evaluate(async()=>{
   try {await fetch('/engine/api/v5/analysis?cache_probe=offline',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});return 'UNEXPECTED_RESPONSE'}catch{return 'NETWORK_REFUSED'}
  })
  expect(outcome).toBe('NETWORK_REFUSED')
  await page.context().setOffline(false)
 }
})
test('new backend real HTTP fixture integrates through isolated proxy',async({page})=>{
 await background(page);await page.clock.install({time:new Date(1800000000000)})
 await page.route('**/engine/api/v5/analysis',r=>r.continue({headers:{...r.request().headers(),'x-qa-scenario':'broker_approved'}}))
 await page.goto('/');const panel=page.getByRole('region',{name:'Manuel Forex analizi',exact:true});await fill(panel)
 await page.getByRole('button',{name:'M15',exact:true}).click();await fill(panel)
 await panel.getByRole('button',{name:'Analiz Et',exact:true}).click()
 await expect(panel.getByText('TEST VERİSİ · Canlı broker kabulü değildir.')).toBeVisible()
 await expect(panel.getByText('Double Top',{exact:true})).toBeVisible()
 await expect(panel.getByTestId('analysis-plan')).toContainText('BLOCKED_BY_EXTERNAL_EVIDENCE')
 await expect(panel.getByTestId('analysis-plan')).not.toContainText('Varsayımsal teknik plan — emir izni yok')
})
test('Tailscale allowed host preserves same-origin proxy contract',async({request})=>{
 const r=await request.get('/engine/openapi.json',{headers:{Host:'pc.example.ts.net'}})
 expect(r.status()).toBe(200);expect((await r.json()).paths['/api/v5/analysis']).toBeTruthy()
})
