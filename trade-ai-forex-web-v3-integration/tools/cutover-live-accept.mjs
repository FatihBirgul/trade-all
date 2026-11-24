import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import {execFileSync} from 'node:child_process'
import {fileURLToPath} from 'node:url'
import {root,sha} from './release-package.mjs'

export function validateManual(symbol,data) {
 if(data.execution_permission!==false||data.market_data_account_mode!=='REAL'||data.account_currency!=='USC'||data.risk_balance_source!=='HYPOTHETICAL_CAPITAL')throw new Error('BLOCK read-only account/hypothetical contract')
 if(data.symbol!==symbol||data.broker_contract?.fields?.broker_symbol?.value!==symbol+'c')throw new Error('BLOCK broker alias identity')
 if(data.spread_status?.policy_status!=='UNAPPROVED'||data.spread_status?.decision!=='BLOCK'||data.spread_status?.max_allowed_price!==null)throw new Error('BLOCK spread policy changed')
 if(['entry_zone','stop_loss','take_profit_1','take_profit_2','lot_size'].some(k=>data[k]!==null))throw new Error('BLOCK unsafe plan exposure')
 if(!['INSUFFICIENT_DATA','NO_TRADE','WAIT','MARKET_CLOSED','STALE_DATA','PROVIDER_UNAVAILABLE'].includes(data.final_decision))throw new Error('BLOCK unexpected decision for blocked policy')
 return true
}
export function validateHistorical(data) {
 if(data.historical_session_evidence?.historical_gap_authorized!==false || data.historical_session_evidence?.status!=='SOURCE_NOT_SUPPLIED')throw new Error('BLOCK historical evidence gate changed')
 return true
}
function identity() {
 const command="$backendOwner=Get-NetTCPConnection -LocalPort 8006 -State Listen | Select-Object -ExpandProperty OwningProcess; $backendProcess=Get-CimInstance Win32_Process -Filter \"ProcessId = $backendOwner\"; @{pid=$backendOwner;created_at_utc=$backendProcess.CreationDate.ToUniversalTime().ToString('o');command=$backendProcess.CommandLine} | ConvertTo-Json -Compress"
 return JSON.parse(execFileSync('powershell.exe',['-NoProfile','-Command',command],{encoding:'utf8',windowsHide:true}))
}
export async function acceptLive({approved=false,manifestPath}) {
 if(!approved)throw new Error('BLOCK explicit operator approval required')
 const relative=path.relative(path.join(root,'.artifacts/cutover'),path.resolve(manifestPath))
 if(relative.startsWith('..')||path.isAbsolute(relative)||!relative)throw new Error('BLOCK private runtime manifest path')
 const raw=fs.readFileSync(manifestPath),startup=JSON.parse(raw)
 if(startup.source_head!=='56cbd7e05a40b106deda9298e2be28b488d0d952'||startup.numpy!=='2.2.6'||startup.port!==8006||startup.mode!=='PRODUCTION_READONLY_NOT_FIXTURE'||startup.execution_permission!==false||!startup.loaded?.loaded_function_code_sha256)throw new Error('BLOCK startup identity')
 if(sha(fs.readFileSync(path.join(root,'tools/cutover-runtime.py')))!==startup.launcher_sha256||sha(fs.readFileSync(path.join(root,'release/reconciled-56cbd7e/runtime-config.json')))!==startup.config_sha256)throw new Error('BLOCK launcher/config drift')
 const before=identity()
 if(before.pid!==startup.pid||!before.command.includes('cutover-runtime.py'))throw new Error('BLOCK process/startup mismatch')
 async function request(route,body) {
  const response=await fetch('http://127.0.0.1:8006'+route,{method:body?'POST':'GET',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(20000)})
  if(!response.ok)throw new Error('BLOCK runtime HTTP '+response.status)
  return response.json()
 }
 const health=await request('/api/v1/health')
 if(health.provider!=='mt5'||health.data_status!=='OK')throw new Error('BLOCK production health')
 const schema=await request('/openapi.json'),serialized=JSON.stringify(schema)
 if(!serialized.includes('broker_contract')||!serialized.includes('spread_status')||Object.keys(schema.paths).some(p=>p.includes('order')))throw new Error('BLOCK runtime schema')
 const symbols=[]
 for(const symbol of ['XAUUSD','EURUSD','GBPUSD','USDJPY']) {
  const meta=(await request('/api/v1/symbols/'+symbol+'/metadata')).data
  if(meta.broker_symbol!==symbol+'c'||meta.account_currency!=='USC'||meta.broker_server!=='Exness-MT5Real50')throw new Error('BLOCK live broker identity')
  const data=await request('/api/v5/analysis',{symbol,timeframe:'M15',confirmations:['H4'],require_private:false,hypothetical_capital:10000,hypothetical_currency:'USC',risk_pct:1})
  validateManual(symbol,data)
  validateHistorical(data)
  symbols.push({symbol,decision:data.final_decision,execution_permission:false,plan:null})
 }
 const after=identity()
 if(after.pid!==before.pid||after.created_at_utc!==before.created_at_utc)throw new Error('BLOCK runtime changed during acceptance')
 const proof={status:'PASS',source_head:startup.source_head,numpy:startup.numpy,port:8006,pid:startup.pid,execution_permission:false,loaded:startup.loaded,process_created_at_utc:after.created_at_utc,accepted_at_utc:new Date().toISOString(),runtime_manifest:path.resolve(manifestPath),runtime_manifest_sha256:sha(raw),symbols}
 const destination=path.join(root,'release/cutover/live-backend-accepted-'+crypto.randomUUID()+'.json')
 fs.writeFileSync(destination,JSON.stringify(proof,null,2),{flag:'wx'})
 return {status:'PASS',receipt:destination,symbols}
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
 const [approval,manifestPath,...extra]=process.argv.slice(2)
 if(approval!=='--operator-approved'||!manifestPath||extra.length)throw new Error('BLOCK explicit operator approval and new runtime manifest required')
 console.log(JSON.stringify(await acceptLive({approved:true,manifestPath}),null,2))
}
