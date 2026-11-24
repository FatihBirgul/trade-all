import {test,expect} from '@playwright/test'
import {response} from '../fixtures.mjs'

async function open(page,answer){
 await page.route('**/news/**',r=>r.fulfill({json:{items:[],events:[],data_status:'DATA_UNAVAILABLE'}}))
 await page.route('**/mt5/**',r=>r.fulfill({json:{candles:[],tick:null}}))
 if(answer)await page.route('**/engine/api/v5/analysis',async r=>r.fulfill({json:answer(r.request().postDataJSON())}))
 await page.goto('/');return page.getByRole('region',{name:'Manuel Forex analizi',exact:true})
}
async function analyze(panel){await panel.getByLabel('Varsayımsal sermaye (USC)').fill('10000');await panel.getByRole('button',{name:'Analiz Et',exact:true}).click()}

test('current USC and risk drafts survive symbol/time changes while stale results clear',async({page})=>{
 const panel=await open(page,()=>response());await panel.getByLabel('Varsayımsal sermaye (USC)').fill('1084,14')
 await panel.getByLabel('Risk oranı (%)').fill('2');await panel.getByRole('button',{name:'Analiz Et',exact:true}).click()
 await panel.getByTestId('analysis-plan').waitFor();await page.locator('#market-symbol').selectOption('EURUSD')
 await expect(panel.getByLabel('Varsayımsal sermaye (USC)')).toHaveValue('1084,14');await expect(panel.getByLabel('Risk oranı (%)')).toHaveValue('2')
 await expect(panel.getByTestId('analysis-plan')).toHaveCount(0);await page.getByRole('button',{name:'M15',exact:true}).click()
 await expect(panel.getByLabel('Varsayımsal sermaye (USC)')).toHaveValue('1084,14');await expect(panel.getByLabel('Risk oranı (%)')).toHaveValue('2')
})

test('merged chart selector keeps all19 symbols but new15 cannot analyze or calculate risk',async({page})=>{
 let calls=0;await page.route('**/engine/api/v5/analysis',()=>{calls++})
 const panel=await open(page);await expect(page.locator('#market-symbol option')).toHaveCount(19)
 await page.locator('#market-symbol').selectOption('AUDJPY')
 await expect(panel.getByRole('button',{name:'Analiz Et',exact:true})).toBeDisabled()
 await expect(page.locator('.risk-calculator').getByRole('button',{name:'Demo Riskini Hesapla'})).toBeDisabled()
 await expect(page.locator('.risk-calculator')).toContainText('yalnız grafik')
 expect(calls).toBe(0)
})

test('explicit cancellation discards late result without automatic retry',async({page})=>{
 let calls=0;await page.route('**/engine/api/v5/analysis',async r=>{
  calls++;await new Promise(resolve=>setTimeout(resolve,400));await r.fulfill({json:response()}).catch(()=>{})
 })
 const panel=await open(page);await analyze(panel)
 await panel.getByRole('button',{name:'Analizi İptal Et'}).click();await page.waitForTimeout(600)
 await expect(panel.getByRole('heading',{name:'Analiz bekleniyor'})).toBeVisible()
 await expect(panel.getByTestId('analysis-plan')).toHaveCount(0);expect(calls).toBe(1)
})

test('historical block wins over otherwise approved synthetic spread and risk',async({page})=>{
 const panel=await open(page,()=>response({historical_session_evidence:{status:'SOURCE_NOT_SUPPLIED',historical_gap_authorized:false}}))
 await analyze(panel);await expect(panel.getByTestId('analysis-plan')).toContainText('BLOCKED_BY_EXTERNAL_EVIDENCE')
 await expect(panel.getByTestId('analysis-plan')).not.toContainText('Varsayımsal teknik plan — emir izni yok')
 await expect(panel.getByText('Kaynak sağlanmadı',{exact:true})).toBeVisible()
})

test('merged current explanation and 8008 source provenance are visible',async({page})=>{
 const panel=await open(page,()=>response({final_decision:'INSUFFICIENT_DATA',data_status:'DATA_UNAVAILABLE',
  decision_reasons:['missing candle during open or unknown historical quote interval'],source_versions:{public_code_sha256:'c'.repeat(64)}}))
 await analyze(panel);await expect(panel).toContainText('Brokerın bu saatlerde kapalı olduğu doğrulanamadı')
 await expect(panel).toContainText('/engine/api/v5/analysis · 8008');await expect(panel).toContainText('c'.repeat(64))
 await expect(panel).toContainText('PRIVATE_PARTIAL');await expect(panel.getByText('TEST / SALT OKUNUR',{exact:true})).toBeVisible()
})

test('390x844 long block messages preserve layout, news and market chart',async({page})=>{
 await page.setViewportSize({width:390,height:844})
 const panel=await open(page,()=>response({final_decision:'INSUFFICIENT_DATA',decision_reasons:['BLOCKED_'+'x'.repeat(3500)],
  historical_session_evidence:{status:'SOURCE_NOT_SUPPLIED',historical_gap_authorized:false}}))
 await analyze(panel);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
 await expect(page.locator('#market-symbol')).toBeVisible();await expect(page.locator('canvas').first()).toBeAttached()
 await expect(page.getByText('Ekonomik Takvim ve Haberler',{exact:true})).toBeAttached()
 await panel.screenshot({path:'.artifacts/final-pwa-mobile-long-block.png'})
})
