# V9 recovery and findings

Start/remote d2bf026885cec0dcbf0ac803a589b5cfdb95b9a0, clean feature branch,
PRIVATE/draft PR1, main4df4b48. Baseline423+152+107=682 rerun, no failures/skips.
All V8 functionality retained; no source migration/replacement engine.

| Severity | Finding | Treatment |
|---|---|---|
|HIGH | Checkpoint returns references to live event dictionaries | Red/green ownership regression; locked deep canonical copy |
|HIGH | Incremental same-instrument frame can switch provider source | Red/green source-binding regression; bind checkpoint/source |
|HIGH | Import check/open path and same-size mutation races | Descriptor walk where supported, pre/open/post identity checks |
|MEDIUM | Bid-only model lacks observed ask execution | Explicit archive capabilities + synchronized paired side replay |
|MEDIUM | Pilot JSON is export-only; cannot validate imported evidence | Strict bounded whitelist/hash/freshness contract, no trust escalation |
|MEDIUM | Research reruns lack preregistration accounting | Frozen external manifest and bounded cross-run disclosure |
|MEDIUM | Decision vs later observation has no immutable journal | Separate hash-bound decision and observed outcome records |

No real MT5/licensed historical/PIT evidence is available. Strong verification and
Gate L stay UNVERIFIED. Later gate/report documents distinguish offline assertions
from unsupported market claims. V9 checkpoint format is versioned; unsigned old
checkpoints require replay rather than silent provenance migration.
