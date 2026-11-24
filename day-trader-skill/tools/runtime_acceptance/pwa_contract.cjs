/* Read-only execution of the PWA's actual pure guards. No PWA files are written. */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');

async function main() {
  const [flag, pwaRoot, fixtureResults, output] = process.argv.slice(2);
  if (flag !== '--inspect-readonly' || !output) {
    throw new Error('Explicit --inspect-readonly <pwa-root> <fixture-results> <output> required');
  }
  const ts = require(path.join(pwaRoot, 'node_modules/typescript'));
  const source = fs.readFileSync(path.join(pwaRoot, 'src/AnalysisPanel.tsx'), 'utf8');
  const pure = source.slice(source.indexOf('type Analysis'), source.indexOf('export default function'));
  const js = ts.transpileModule(pure, {compilerOptions: {target: ts.ScriptTarget.ES2022}}).outputText;
  const guards = vm.runInNewContext(js+'; ({isAnalysis, approved})', {}, {timeout: 1000});
  const fixtures = JSON.parse(fs.readFileSync(fixtureResults, 'utf8'));
  const hypothetical = {...fixtures.responses.top, provider: 'mt5'};
  const eligible = {...hypothetical, trading_eligibility: 'ELIGIBLE'};
  const check = (name, ok) => {if (!ok) throw new Error(name); return name;};
  const checks = [
    check('current_hypothetical_request_fields', source.includes('hypothetical_capital: balanceValue') &&
      source.includes("hypothetical_currency: 'USC'") && !source.includes('balance: 10000')),
    check('synthetic_mt5_shape_accepts_additive_patterns', guards.isAnalysis(hypothetical)),
    check('hypothetical_not_evaluated_plan_hidden', !guards.approved(hypothetical)),
    check('eligible_valid_geometry_plan_visible', guards.approved(eligible)),
    check('null_plan_hidden', !guards.approved({...eligible, entry_zone: null})),
    check('wrong_symbol_result_checked', source.includes('value.symbol !== symbol')),
    check('gbpusd_usdjpy_gate_still_missing', source.includes("(symbol === 'XAUUSD' || symbol === 'EURUSD')")),
    check('pattern_renderer_missing', !source.includes('chart_patterns')),
    check('account_currency_response_missing', !source.includes('account_currency')),
  ];
  const result = {checks, count: checks.length, source_sha256: crypto.createHash('sha256').update(source).digest('hex'),
    scope: 'READ_ONLY_SOURCE_AND_EXECUTED_PURE_GUARDS_SYNTHETIC_MT5_SHAPE_NOT_LIVE_UI',
    findings: {request_compatible: true, additive_response_compatible: true,
      hypothetical_plan_hidden: true, patterns_rendered: false, four_symbol_analysis_enabled: false}};
  fs.writeFileSync(output, JSON.stringify(result, null, 2));
  console.log(`PASS ${checks.length} PWA contract checks; no PWA files changed`);
}
main().catch(error => {console.error(error.message); process.exitCode = 1;});
