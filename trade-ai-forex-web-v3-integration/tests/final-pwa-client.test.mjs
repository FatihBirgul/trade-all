import {test} from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import {response} from './fixtures.mjs'
import {parseAnalysis,planVisibility,explainReason} from '../.artifacts/unit/contract.mjs'
const parse=raw=>parseAnalysis(raw,raw.symbol,raw.timeframe)
for(const historical of [undefined,null,{}, {status:'SOURCE_NOT_SUPPLIED',historical_gap_authorized:false},
 {status:'HISTORICAL_SOURCE_VERIFIED',historical_gap_authorized:true,cross_source_reconciled:false,evidence_ids:['fixture']}])
test('missing/conflicting historical evidence cannot expose an otherwise passing plan '+JSON.stringify(historical),()=>{
 const result=planVisibility(parse(response({historical_session_evidence:historical})))
 assert.equal(result.showPlan,false);assert.match(result.blockers.join(' '),/BLOCKED_BY_EXTERNAL_EVIDENCE/)
})
test('current user historical-gap explanation is preserved for both backend reasons',()=>{
 for(const reason of ['missing candle during open or unknown historical quote interval','missing candle without verified broker hours'])
 assert.match(explainReason(reason),/Brokerın bu saatlerde kapalı olduğu doğrulanamadı/)
})
test('fresh recorded real9792 responses retain source and historical diagnostics',()=>{
 const evidence=JSON.parse(fs.readFileSync('release/final-pwa-56cbd7e/live-api.json'))
 assert.equal(evidence.fixture,false)
 for(const raw of Object.values(evidence.responses)){
  const data=parse(raw);assert.equal(planVisibility(data).showPlan,false)
  assert.equal(data.historical_session_evidence.historical_gap_authorized,false)
  assert.equal(data.source_versions.public_code_sha256,raw.source_versions.public_code_sha256)
  assert.equal(data.account_currency,'USC');assert.equal(data.execution_permission,false)
 }
})
test('new chart symbols cannot be parsed as V5 analysis scope',()=>{
 for(const symbol of ['AUDUSD','CHFJPY','AUDJPY'])assert.throws(()=>parse(response({symbol})))
})
test('minimum lot risk refusal hides plan even with synthetic reviewed history',()=>{
 const raw=response({risk_policy:{decision:'BLOCK'},lot_size:null,decision_reasons:['minimum lot exceeds risk budget']})
 assert.equal(planVisibility(parse(raw)).showPlan,false);assert.match(explainReason(raw.decision_reasons[0]),/Minimum lot/)
})
