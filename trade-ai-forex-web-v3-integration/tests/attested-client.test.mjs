import {test} from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import {parseAnalysis,planVisibility} from '../.artifacts/unit/contract.mjs'

const acceptance=JSON.parse(fs.readFileSync('release/attested-8008-56cbd7e/acceptance.json'))
for(const name of ['primary','failback']) {
 test('RC consumes four actual attested '+name+' refusals safely',()=>{
  for(const [symbol,data] of Object.entries(acceptance[name].responses)) {
   const parsed=parseAnalysis(data,symbol,'M15')
   assert.equal(parsed.execution_permission,false)
   assert.equal(parsed.trading_eligibility,'BLOCKED')
   assert.equal(planVisibility(parsed).showPlan,false)
   assert.equal(data.spread_status.policy_status,'UNAPPROVED')
   assert.equal(data.historical_session_evidence.historical_gap_authorized,false)
  }
 })
}
