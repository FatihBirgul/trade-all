import {test,expect} from '@playwright/test'
import {response} from '../fixtures.mjs'

test('editing preserved USC draft cancels pending result and requires a fresh manual request',async({page})=>{
 await page.route('**/news/**',r=>r.fulfill({json:{items:[],events:[],data_status:'DATA_UNAVAILABLE'}}))
 await page.route('**/mt5/**',r=>r.fulfill({json:{candles:[],tick:null}}))
 const requests=[]
 let releaseFirst
 const first=new Promise(resolve=>{releaseFirst=resolve})
 await page.route('**/engine/api/v5/analysis',async route=>{
  requests.push(route.request().postDataJSON())
  if(requests.length===1)await first
  await route.fulfill({json:response()}).catch(()=>{})
 })
 await page.goto('/')
 const panel=page.getByRole('region',{name:'Manuel Forex analizi',exact:true})
 const capital=panel.getByLabel('Varsayımsal sermaye (USC)')
 const analyze=panel.getByRole('button',{name:'Analiz Et',exact:true})
 await capital.fill('10000');await analyze.click()
 await expect.poll(()=>requests.length).toBe(1)
 await capital.fill('15000');releaseFirst()
 await expect(panel.getByRole('heading',{name:'Analiz bekleniyor',exact:true})).toBeVisible()
 await expect(panel.getByTestId('analysis-plan')).toHaveCount(0)
 await expect(capital).toHaveValue('15000')
 expect(requests).toHaveLength(1)
 await analyze.click();await expect(panel.getByTestId('analysis-plan')).toBeVisible()
 expect(requests).toHaveLength(2)
 expect(requests[0].hypothetical_capital).toBe(10000)
 expect(requests[1].hypothetical_capital).toBe(15000)
 expect(requests[1].hypothetical_currency).toBe('USC')
})
