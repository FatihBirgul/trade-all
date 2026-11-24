# V9 causal structure and pattern audit

Two independently reproduced HIGH risks were fixed: checkpoint export exposed
live event dictionaries, and incremental updates could switch provider source
without changing instrument. Export/view now take locked owned canonical copies;
ledger and restored history bind provider source as well as instrument/timeframe.
Restore validates historical candle QC, finality, chronology, watermark, event
sequence/geometry and source. Old snapshot requests still cannot observe newer
state; closed-bar revision is refused. Red/green regressions are in
 test_v9_recovery.py; retained V7/V8 lifecycle, eviction, replay and concurrency
regressions continue unchanged. No pattern threshold was relaxed.

Checkpoint format fx-fvg-ledger-v9-1 is intentionally versioned. Unsigned V8
checkpoints require rebuilding by replay, rather than silently migrating trust.
A hash detects accidental inconsistency, not an adversary able to recompute it.
Optional CheckpointStore is off by default; explicit existing root must be within
this checkout's state/v9; opaque names,16-file quota,400KB/file, own atomic staging,
fsync and identity/source/timeframe load checks. It never evicts user files or
connects production DB/old V2 ledger. Operator-controlled root is required.

Eleven candle extensions, sixteen chart geometries, retained V2 catalogue and
confirmed divergence are preserved. V7 family positive/flat-negative/mirror/tick/
scale/prefix fixtures and V8 translation/invalid-decisive-body/noise/finality/
source controls remain. V9 adds state ownership/source/restore evidence, not a
new per-family labelled study. See V8_PATTERN_VALIDATION.md and existing pattern
catalogue for each family's timing/status metadata.

Priority gaps: (1) labelled breakout/retest and pivot-confirmation boundary cases;
(2) missing-session/invalidation/expiry adversarial examples for every family;
(3) real-OHLC scale/venue variation; (4) subjective rounding annotations. Complete
family-specific adversarial timing coverage is PARTIAL; rounding remains
EXPERIMENTAL. New real-market labelled validation is MISSING. Detections remain
descriptive, without calibrated probability or independent directional authority.
Unlabelled random-path match rates are not false-positive/false-negative rates.
