import {test} from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import {parseAnalysis,planVisibility} from '../.artifacts/unit/contract.mjs'

const acceptance=JSON.parse(fs.readFileSync('release/runtime8008-56cbd7e/api-acceptance.json'))
test('RC consumes all four actual8008 safe refusals without plan exposure',()=>{
 for(const [symbol,raw] of Object.entries(acceptance.responses)) {
  const parsed=parseAnalysis(raw,symbol,'M15')
  assert.equal(parsed.trading_eligibility,'BLOCKED')
  assert.equal(parsed.execution_permission,false)
  assert.equal(planVisibility(parsed).showPlan,false)
 }
})
test('actual8008 response remains compatible when additive historical field is absent',()=>{
 for(const [symbol,raw] of Object.entries(acceptance.responses)) {
  const legacy={...raw};delete legacy.historical_session_evidence
  assert.equal(parseAnalysis(legacy,symbol,'M15').trading_eligibility,'BLOCKED')
 }
})
