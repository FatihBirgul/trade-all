# V9 optional forward observation journal

DecisionJournal is opt-in; API app.state.decision_journal defaults to None.
No endpoint, scheduler, service, automatic paper trade or order execution added.
A configured journal records immutable canonical analysis ID/time, symbol/provider/
broker/timeframe, source/strategy/snapshot identity, decision/reasons/risk veto,
entry/SL/TP if present, expiry, market status, freshness and macro context.

Capacity1..512 (default256),64KB per decision,32 observations per decision. Exported
records are owned copies; analysis-ID hash conflicts refuse rewriting. Oldest
records may be evicted at capacity; process restart loses memory. Explicit export/
durable audit infrastructure is a future operational concern.

At decision time future status is NOT_OBSERVED. `observe` accepts only timestamps
strictly after the decision and no later than the supplied as-of; observations
are chronological/deduplicated and bind the original decision hash. Outcomes do
not rewrite a decision. Labels are SIMULATED_OBSERVATION_NOT_BROKER_EXECUTION;
no actual execution, fill quality or realized broker PnL is inferred. No forward
market observations were collected during this task.
