import React, { useState } from "react";
import { router } from "expo-router";
import { comparable } from "../src/domain/records";
import {
  filterHistory,
  recordedDecision,
  type HistoryFilters,
} from "../src/domain/history";
import { type Analysis, symbols, timeframes } from "../src/domain/safety";
import { useApp } from "../src/state";
import { usePage } from "../src/usePage";
import { usePagedHistory } from "../src/usePagedHistory";
import { directionText } from "../src/domain/presentation";
import {
  Button,
  Card,
  Choices,
  Disclosure,
  Empty,
  Failure,
  Heading,
  Label,
  Loading,
  Page,
} from "../src/ui";
export default function History() {
  const app = useApp();
  const scope = [
    app.mode,
    app.connectionKey,
    app.config.origin,
    app.config.session,
    app.mode === "demo" ? app.history.length : "live",
  ].join("|");
  const [filters, setFilters] = useState<HistoryFilters>({
    symbol: "Tümü",
    timeframe: "Tümü",
    account: "Tümü",
    decision: "Tümü",
    order: "Yeni → Eski",
  });
  const [selection, setSelection] = useState<{
    scope: string;
    analysis: Analysis;
  } | null>(null);
  const selected = selection?.scope === scope ? selection.analysis : null;
  const q = usePagedHistory(
    async (offset) => {
      if (app.mode === "demo")
        return app.history
          .filter((a) => a.data_mode === "fixture")
          .slice(offset, offset + 20);
      const rows = await app.api.analyses(offset);
      if (
        rows.some(
          (a) =>
            a.data_mode !== "live" ||
            (app.sessionInfo?.accounts &&
              !app.sessionInfo.accounts.includes(a.risk_portfolio)),
        )
      )
        throw new Error("Geçmiş kaydının hesabı/veri modu doğrulanamadı.");
      return rows;
    },
    scope,
    app.mode === "live" && app.sessionInfo?.accounts.length === 1,
  );
  const rows = filterHistory(q.rows, filters);
  const displayPage = usePage(scope + "|" + JSON.stringify(filters));
  const visibleRows = rows.slice(displayPage.offset, displayPage.offset + 20);
  function refreshHistory() {
    displayPage.reset();
    q.reload();
  }
  function choose(key: keyof HistoryFilters, value: string) {
    setFilters((f) => ({ ...f, [key]: value }));
    if (key !== "order") setSelection(null);
  }
  return (
    <Page mode={app.mode} connection={app} headerShown>
      <Heading>Analiz geçmişi</Heading>
      <Disclosure title="Filtreler ve sıralama">
        <Choices
          values={["Tümü", ...symbols]}
          value={filters.symbol}
          onChange={(v) => choose("symbol", v)}
        />
        <Choices
          values={["Tümü", ...timeframes]}
          value={filters.timeframe}
          onChange={(v) => choose("timeframe", v)}
        />
        <Choices
          values={[
            "Tümü",
            ...(app.mode === "live"
              ? (app.sessionInfo?.accounts ?? ["AUTO", "MANUAL"])
              : ["AUTO", "MANUAL"]),
          ]}
          value={filters.account}
          onChange={(v) => choose("account", v)}
        />
        <Choices
          values={["Tümü", "BEKLE", "Yükseliş", "Düşüş"]}
          value={filters.decision}
          onChange={(v) => choose("decision", v)}
        />
        <Choices
          values={["Yeni → Eski", "Eski → Yeni"]}
          value={filters.order}
          onChange={(v) => choose("order", v)}
        />
      </Disclosure>
      <Label muted>
        {rows.length} eşleşme / {q.rows.length} yüklenen kayıt · filtreler
        yüklenen kayıtlara uygulanır.
      </Label>
      <Button
        title="Geçmişi yenile"
        variant="ghost"
        disabled={q.loading}
        onPress={refreshHistory}
      />
      {selected ? (
        <>
          <Label>
            Seçilen: {selected.symbol} · {selected.timeframe} ·{" "}
            {selected.risk_portfolio}
          </Label>
          <Button
            title="Karşılaştırma seçimini kaldır"
            variant="ghost"
            onPress={() => setSelection(null)}
          />
        </>
      ) : null}
      {q.error ? (
        <Failure
          message={"Son kayıtlar güncel değil. " + q.error}
          retry={refreshHistory}
        />
      ) : null}
      {q.loading && !q.rows.length ? (
        <Loading />
      ) : visibleRows.length ? (
        visibleRows.map((a) => (
          <Card key={a.analysis_id}>
            <Label style={{ fontWeight: "700" }}>
              {a.symbol} · {a.timeframe} ·{" "}
              {recordedDecision(a) === "WAIT"
                ? "BEKLE"
                : directionText(recordedDecision(a))}
            </Label>
            <Label muted>
              {a.risk_portfolio} ·{" "}
              {a.data_mode === "fixture" ? "DEMO örneği" : "CANLI kayıt"} ·{" "}
              {new Date(a.created_at_ms).toLocaleString("tr-TR")}
            </Label>
            {selected && comparable(selected, a) ? (
              <Button
                title="Seçilen kayıtla karşılaştır"
                secondary
                onPress={() =>
                  router.push({
                    pathname: "/detail",
                    params: {
                      id: a.analysis_id,
                      compare: selected.analysis_id,
                    },
                  })
                }
              />
            ) : null}
            {selected?.analysis_id !== a.analysis_id ? (
              <Button
                title="Karşılaştırma için seç"
                variant="ghost"
                onPress={() => setSelection({ scope, analysis: a })}
              />
            ) : null}
            <Button
              title="Detayı aç"
              variant="ghost"
              onPress={() =>
                router.push({
                  pathname: "/detail",
                  params: { id: a.analysis_id },
                })
              }
            />
          </Card>
        ))
      ) : !q.loading ? (
        <Empty text="Yüklenen kayıtlarda filtreye uygun analiz yok. Daha eski kayıtları yükleyebilir veya filtreleri değiştirebilirsiniz." />
      ) : null}
      {rows.length > 20 ? (
        <>
          <Label muted>
            {displayPage.offset + 1}–
            {Math.min(displayPage.offset + 20, rows.length)} / {rows.length}{" "}
            eşleşme
          </Label>
          <Button
            title="Önceki eşleşmeler"
            variant="ghost"
            disabled={displayPage.offset === 0}
            onPress={displayPage.previous}
          />
          <Button
            title="Sonraki eşleşmeler"
            variant="ghost"
            disabled={displayPage.offset + 20 >= rows.length}
            onPress={displayPage.next}
          />
        </>
      ) : null}
      <Button
        title={q.loading ? "Yükleniyor…" : "Daha eski kayıtları yükle"}
        secondary
        disabled={q.loading || !q.hasMore || !!q.error}
        onPress={q.more}
      />
      <Label muted>
        Kaydedilen karar, analiz anındaki güvenlik kontrolüyle gösterilir.
        Tarihsel kayıt güncel fırsat değildir. En çok 400 kayıt; istatistik veya
        başarı yüzdesi üretilmez.
      </Label>
    </Page>
  );
}
