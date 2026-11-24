import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import {pathToFileURL} from 'node:url'
import ts from 'typescript'
import {response} from './fixtures.mjs'

const folder=path.resolve('.artifacts/unit');await fs.mkdir(folder,{recursive:true})
for(const name of ['contract','client']) {
  const source=await fs.readFile('src/analysis/'+name+'.ts','utf8')
  let js=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText
  js=js.replace("from './contract'","from './contract.mjs'")
  await fs.writeFile(path.join(folder,name+'.mjs'),js)
}
const {capitalInput,parseAnalysis,planVisibility,freshness,explainReason}=await import(pathToFileURL(path.join(folder,'contract.mjs')))
const {requestAnalysis}=await import(pathToFileURL(path.join(folder,'client.mjs')))
const parse=(raw)=>parseAnalysis(raw,raw.symbol,raw.timeframe)

test('four canonical symbols accepted without frontend alias generation',()=>{
 for(const symbol of ['XAUUSD','EURUSD','GBPUSD','USDJPY']) assert.equal(parse(response({symbol})).symbol,symbol)
})
for(const decision of ['BUY_CANDIDATE','SELL_CANDIDATE','WAIT','NO_TRADE','INSUFFICIENT_DATA','MARKET_CLOSED','STALE_DATA','PROVIDER_UNAVAILABLE']) {
 test('real V5 decision '+decision,()=>assert.equal(parse(response({final_decision:decision})).final_decision,decision))
}
test('valid hypothetical plan remains NOT_EVALUATED',()=>{
 const a=parse(response());assert.equal(planVisibility(a).showPlan,true);assert.equal(a.trading_eligibility,'NOT_EVALUATED');assert.equal(a.execution_permission,false)
})
test('sell geometry',()=>{
 const a=parse(response({final_decision:'SELL_CANDIDATE',legacy_signal:'SELL',stop_loss:2010,take_profit_1:1980,take_profit_2:1970}));assert.equal(planVisibility(a).showPlan,true)
})
for(const [name,overrides] of Object.entries({
  'unapproved spread':{spread_status:{policy_status:'UNAPPROVED',decision:'BLOCK',max_allowed_price:null}},
  'unknown session':{market_status:'UNKNOWN'},'close only':{market_status:'DISABLED'},
  'unverified contract':{broker_contract:{status:'UNVERIFIED'}},'missing safety fields':{broker_contract:undefined,spread_status:undefined},
  'missing risk':{risk_policy:null},'null lot':{lot_size:null},'null entry':{entry_zone:null},
  'currency USD':{account_currency:'USD'},'currency USDC':{account_currency:'USDC'},
  'broker balance':{risk_balance_source:'BROKER_VERIFIED_DEMO'},'execution true':{execution_permission:true},
  'execution unknown':{execution_permission:undefined},'source mode unknown':{market_data_account_mode:'UNVERIFIED'},
  'snapshot absent':{snapshot_id:null},'blocked eligibility':{trading_eligibility:'BLOCKED'},
  'data unavailable':{data_status:'DATA_UNAVAILABLE'},'legacy mismatch':{legacy_signal:'SELL'},
  'missing risk reward':{risk_reward:null},'bad second target':{take_profit_2:1980},'broker identity mismatch':{broker_symbol:'EURUSDc'},
})) test('hide plan: '+name,()=>assert.equal(planVisibility(parse(response(overrides))).showPlan,false))
test('stale and future results are never current',()=>{
 const a=parse(response());const now=Date.parse(a.as_of_utc)
 assert.equal(freshness(a,now+120001),'STALE');assert.equal(planVisibility(a,now+120001).showPlan,false)
 assert.equal(freshness(a,now-6000),'FUTURE')
})
test('capital is user-supplied USC, comma accepted, risk max five',()=>{
 assert.deepEqual(capitalInput('2500,50','1'),{hypothetical_capital:2500.5,hypothetical_currency:'USC',risk_pct:1})
 for(const [c,r] of [['','1'],['0','1'],['100','0'],['100','6'],['-1','1'],['Infinity','1']]) assert.throws(()=>capitalInput(c,r))
})
test('wrong symbol/time/schema/provider fails closed',()=>{
 for(const changes of [{symbol:'EURUSD'},{timeframe:'D1'},{schema_version:'other'},{provider:'unknown'},{as_of_utc:'yesterday'}]) assert.throws(()=>parseAnalysis(response(changes),'XAUUSD','M5'))
})
test('pattern source mismatch hides incompatible items without directional votes',()=>{
 const raw=response();raw.chart_patterns.items[0].source_sha256='c'.repeat(64)
 const a=parse(raw);assert.equal(a.chart_patterns.sourceMismatch,true);assert.equal(a.chart_patterns.items.length,0)
 assert.equal(a.final_decision,'BUY_CANDIDATE')
})
test('null first-known does not become geometric pivot time',()=>{
 const raw=response();raw.chart_patterns.items[0].first_known_utc=null
 assert.equal(parse(raw).chart_patterns.items[0].first_known_utc,null)
})
test('old schema still parses, unknown safety does not become PASS',()=>{
 const raw=response();delete raw.broker_contract;delete raw.spread_status
 assert.equal(parse(raw).schema_version,'forex-analysis-5');assert.equal(planVisibility(parse(raw)).showPlan,false)
})
test('source/approval and minimum lot refusals explained in Turkish',()=>{
 assert.match(explainReason('minimum lot exceeds risk budget'),/Minimum lot/)
 assert.match(explainReason('missing candle without verified broker hours'),/seans/)
})
test('request sends hypothetical capital only and D1 compatible confirmation',async()=>{
 const previous=globalThis.fetch;let payload
 globalThis.fetch=async(_url,options)=>{payload=JSON.parse(options.body);return new Response(JSON.stringify(response({timeframe:'D1'})))}
 try {await requestAnalysis('XAUUSD','D1','2500','1',new AbortController().signal);assert.deepEqual(payload.confirmations,['D1']);assert.equal(payload.hypothetical_currency,'USC');assert.equal('balance' in payload,false)} finally {globalThis.fetch=previous}
})
test('503 never reflects private server reason',async()=>{
 const previous=globalThis.fetch;globalThis.fetch=async()=>new Response(JSON.stringify({detail:{status:'DATA_UNAVAILABLE',reason:'C:/private/token'}}),{status:503})
 try {await assert.rejects(requestAnalysis('XAUUSD','M5','10','1',new AbortController().signal),e=>e.message.includes('503')&&!e.message.includes('private'))} finally {globalThis.fetch=previous}
})
test('timeout produces safe explicit refusal',async()=>{
 const previous=globalThis.fetch;globalThis.fetch=async(_url,options)=>new Promise((_resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new TypeError('aborted'))))
 try {await assert.rejects(requestAnalysis('XAUUSD','M5','10','1',new AbortController().signal,5),/zaman aşımı/)} finally {globalThis.fetch=previous}
})
