import {test} from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import {validateHistorical} from '../tools/cutover-live-accept.mjs'

test('new release accepts only a missing, unauthorized historical registry',()=>{
 assert.equal(validateHistorical({historical_session_evidence:{status:'SOURCE_NOT_SUPPLIED',historical_gap_authorized:false}}),true)
 for(const value of [undefined,{status:'HISTORICAL_SOURCE_VERIFIED',historical_gap_authorized:true},{status:'CURRENT_WEEKLY_ONLY',historical_gap_authorized:false}]) {
  assert.throws(()=>validateHistorical({historical_session_evidence:value}),/BLOCK/)
 }
})
test('new apply and startup acceptance reject the previous backend SHA',()=>{
 for(const name of ['promotion-apply.mjs','cutover-live-accept.mjs','cutover-isolated-check.py','cutover-e2e.mjs']) {
  const source=fs.readFileSync('tools/'+name,'utf8')
  assert.equal(source.includes('3c8adb810058b4738640f46bde84de8ec12205ad'),false)
 }
})
test('unchanged client accepts old and new real HTTP response fields',async()=>{
 const {parseAnalysis}=await import('../.artifacts/unit/contract.mjs')
 const data=JSON.parse(fs.readFileSync('.artifacts/release-backend311-historical.json')).responses.none
 assert.equal(parseAnalysis(data,'XAUUSD','M15').trading_eligibility,'BLOCKED')
 const legacy={...data};delete legacy.historical_session_evidence
 assert.equal(parseAnalysis(legacy,'XAUUSD','M15').trading_eligibility,'BLOCKED')
})
