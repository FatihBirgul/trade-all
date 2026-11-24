# V9 research integrity and local preregistration

Retained V2 train/select/freeze/test and bounded ExperimentRegistry remain.
HistoricalDataset owns bid/ask tuples, all rules/cost epochs and their hashes.
Held-out ask mutation changes experiment identity but not prior frozen training
selection: independently checked in test_v9_pit_safety.py. Ask prefixes are cropped
at the same cutoff as bid. Replay mode distinguishes SYNTHETIC_MECHANICAL_TEST,
BID_ONLY_MODELLED_SPREAD and DECLARED_COST_REPLAY; VERIFIED mode is unavailable.

`research_protocol.prepare(dataset,config)` exports a canonical body with dataset,
rules/cost hashes, code hash, versions/configuration, folds and train/validation/
test cutoffs, candidate count, seed/configuration and deterministic selection
criterion. registered_at is recorded separately from protocol identity.
`verify` refuses changed data/rules/cost/code/configuration. This is
LOCAL_DECLARATION_NOT_EXTERNAL_PREREGISTRATION, not external timestamp attestation.

Optional run_oos registration/trial_registry/campaign arguments bind execution.
TrialRegistry bounds16 campaigns and1..100 attempts each, freezes budget, counts
all started attempts and records COMPLETED/CANCELLED/FAILED. Post-run validation
and publication failures are accounted for; no partial success is advertised.
Exports are owned copies under locks. Existing cancellation is cooperative, not
an atomic forced kill at every possible publication boundary.

Process memory resets on restart; redeclaring another campaign or using other
processes is outside this accounting. Export the declaration and all attempts
before examining OOS; external immutable timestamping/global trial registry is
still PARTIAL. Repeated use of the same OOS set is not independent market evidence.
No actual permitted market dataset was supplied: INSUFFICIENT_EVIDENCE remains.
Evidence: test_v8_research_control.py, test_v9_protocol_journal.py,
test_v9_pit_safety.py and retained V2 walk-forward regressions.
