import React, { useState } from "react";
import { useApp } from "./state";
import { useResource } from "./resource";
import { snapshotMatches } from "./domain/snapshot";
import type { Analysis } from "./domain/safety";
import { SnapshotChart } from "./SnapshotChart";
import { Button, Card, Failure, Heading, Loading } from "./ui";
export function SnapshotPanel({
  analysis,
  levelsAllowed,
}: {
  analysis: Analysis;
  levelsAllowed: boolean;
}) {
  const app = useApp();
  const [load, setLoad] = useState(false);
  const scope = [
    app.mode,
    app.connectionKey,
    app.config.session,
    analysis.analysis_id,
    load,
  ].join("|");
  const query = useResource(async () => {
    if (!load || app.mode !== "live") return null;
    const snapshot = await app.api.candles(
      analysis.analysis_id,
      analysis.timeframe,
    );
    if (!snapshotMatches(analysis, snapshot))
      throw new Error("Analiz mumlarının kaynağı doğrulanamadı.");
    return snapshot;
  }, scope);
  if (app.mode !== "live") return null;
  return (
    <Card>
      <Heading>Analizin mum kaydı</Heading>
      {!load ? (
        <Button
          title="Analiz mumlarını yükle"
          secondary
          onPress={() => setLoad(true)}
        />
      ) : query.loading ? (
        <Loading />
      ) : query.error ? (
        <Failure message={query.error} retry={query.reload} />
      ) : query.data ? (
        <SnapshotChart
          key={query.data.analysis_id + "|" + app.uiMode}
          snapshot={query.data}
          pro={app.uiMode === "pro"}
          levels={levelsAllowed ? analysis.levels : null}
        />
      ) : null}
    </Card>
  );
}
