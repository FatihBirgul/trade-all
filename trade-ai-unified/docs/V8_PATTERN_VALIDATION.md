# V8 pattern validation lab

No new pattern names were added. The retained V2 catalogue, V7 eleven candle
extensions and sixteen chart geometries remain the subject of QA. pattern_lab
provides version/id, bars/pivots, tick policy, first-known/confirmation/expiry/
invalidation, source evidence and confidence semantics. All detections are
DESCRIPTIVE/NON_DIRECTIONAL; no calibrated win probability.

VERIFIED_OFFLINE: V7 per-family positive/flat-negative/mirror/tick/scale/prefix
fixtures retained; V8 adds all-extension translation and invalid decisive-body
controls, line-family translation/scale/nonstructural noise, invalid OHLC/finality/
source/missing/future snapshot rejection. Chart extension and candle extension now
validate their direct frame entry points, not only the outer engine. Existing V2
pivot/slope helpers remain in use. tests/test_v7_candles.py, test_v7_charts.py,
test_v8_pattern_lab.py and test_v8_audit.py are the reproducible evidence.

V8_PATTERN_LAB_RESULTS.json measures12 fixed-seed816 random paths. Detection rates
are fractions of UNLABELLED synthetic random paths with a rule match. They are NOT
market false-positive rates, accuracy or expected win rates. Missing hits on a
random path are not false negatives. No thresholds were relaxed to improve counts.
Complete labelled/adversarial real-OHLC timing coverage for every old/new family
remains PARTIAL; rounding stays EXPERIMENTAL. No family was promoted to trading
authority. Existing family catalogue does not establish market usefulness.
