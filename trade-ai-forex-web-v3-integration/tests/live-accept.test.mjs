import {test} from 'node:test'
import assert from 'node:assert/strict'
import {spawnSync} from 'node:child_process'
import {root} from '../tools/release-package.mjs'
import {validateManual,acceptLive} from '../tools/cutover-live-accept.mjs'

const safe=()=>({symbol:'XAUUSD',execution_permission:false,market_data_account_mode:'REAL',account_currency:'USC',risk_balance_source:'HYPOTHETICAL_CAPITAL',broker_contract:{fields:{broker_symbol:{value:'XAUUSDc'}}},spread_status:{policy_status:'UNAPPROVED',decision:'BLOCK',max_allowed_price:null},entry_zone:null,stop_loss:null,take_profit_1:null,take_profit_2:null,lot_size:null,final_decision:'INSUFFICIENT_DATA'})
test('safe observed refusal passes',()=>assert.equal(validateManual('XAUUSD',safe()),true))
for(const [field,value] of [['execution_permission',true],['account_currency','USD'],['risk_balance_source','REAL_BALANCE'],['market_data_account_mode','DEMO'],['entry_zone',{low:1,high:2}],['lot_size',.01],['final_decision','BUY_CANDIDATE']])test('rejects '+field,()=>assert.throws(()=>validateManual('XAUUSD',{...safe(),[field]:value}),/BLOCK/))
test('rejects broker alias substitution',()=>assert.throws(()=>validateManual('EURUSD',safe()),/BLOCK/))
test('rejects unapproved spread becoming pass',()=>{const d=safe();d.spread_status.decision='PASS';assert.throws(()=>validateManual('XAUUSD',d),/BLOCK/)})
test('cannot inspect live runtime without separate approval',async()=>await assert.rejects(acceptLive({manifestPath:'not-read'}),/approval required/))
test('CLI refuses missing explicit operation approval',()=>{const r=spawnSync(process.execPath,['tools/cutover-live-accept.mjs'],{cwd:root,encoding:'utf8'});assert.notEqual(r.status,0);assert.match(r.stderr,/explicit operator approval/)})
