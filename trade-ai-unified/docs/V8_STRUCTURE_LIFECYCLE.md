# V8 causal structure and FVG history

Historical swing/equality/zone tolerances are now frozen at first-known using that
prefix's trailing true-range mean. A later ATR cannot relabel an old HH as equality.
The red/green regression in test_v8_audit.py establishes this causal correction.
V5 pivots and V2 price action remain the underlying sources.

structure_ledger.StructureLedger observes closed bars with identity/QC checks.
FVG creation reuses the V2 three-candle displacement/ATR geometry, with explicit
minimum tick. It retains DETECTED→CONFIRMED→PARTIALLY_FILLED→MITIGATED, or INVALIDATED/
EXPIRED transitions as appropriate. Origin, first-known and transition times differ.
Full wick mitigation is distinct from closed invalidation. Fill fraction is geometric;
re-entry counts discontinuous touches, never actual institutional orders/volume.

Capacity128 events(default), max256;15 bars of warm-up state; explicit expiry.
Checkpoint body/hash/schema, candle identity, event geometry/version/chronology and
cardinality checks support deterministic restore/replay. Hash is integrity, not
authentication. API uses a locked24-key provider-owned process store; replacing
provider starts fresh. Oldest events evict; process restart requires a checkpoint
or closed-bar replay. Deep persistent cross-process history is NOT supplied.

Rolling updates retain prior events within bounds. Missing incremental history or
historical revision is refused. A newer shared ledger MUST NOT be read by an older
request: V8 final concurrency regression reproduces this and now fails closed.
Historical callers use independent replay/checkpoints. FVG context has no strategy
vote, so eviction/unknown history cannot silently create directional permission.
Tests: test_v8_structure_ledger.py creation/partial/full/invalid/expiry/restart/
rolling/identity/revision/ahead-of-snapshot; test_v8_failure_branches.py tampering.
