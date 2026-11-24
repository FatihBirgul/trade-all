import { EquityHistoryPanel } from "../src/EquityHistoryPanel";
import React, { useState } from "react";
import { useApp } from "../src/state";
import { useResource } from "../src/resource";
import { performanceForAccount, pnlWindow } from "../src/domain/portfolio";
import { money } from "../src/domain/safety";
import { MiniPriceChart } from "../src/MiniPriceChart";
import {
  Button,
  Choices,
  Card,
  Empty,
  Failure,
  Heading,
  Loading,
  Page,
  Row,
  Label,
} from "../src/ui";
export default function Performance() {
  const app = useApp();
  const [loadGraph, setLoadGraph] = useState(false);
  const scope = [
    app.mode,
    app.account,
    app.connectionKey,
    app.config.origin,
    app.config.session,
  ].join("|");
  const q = useResource(async () => {
    const data =
      app.mode === "demo"
        ? {
            portfolios: ["AUTO", "MANUAL"].map((portfolio_id) => ({
              portfolio_id,
              ambiguous_positions: 0,
              closed_positions: 0,
              wins: 0,
              losses: 0,
              win_rate: null,
              realized_pnl_quote: "0",
              fees_quote: "0",
            })),
          }
        : await app.api.performance();
    return performanceForAccount(data.portfolios, app.account);
  }, scope);
  const graph = useResource(
    async () =>
      loadGraph && app.mode === "live"
        ? pnlWindow(await app.api.transactions(app.account, 0), app.account)
        : [],
    scope + "|" + loadGraph,
  );
  const p = q.data;
  return (
    <Page mode={app.mode} connection={app} headerShown>
      {app.mode === "demo" ? (
        <Label muted>Yerel DEMO · gerçek hesap performansı sorgulanmaz.</Label>
      ) : null}
      <Choices
        values={["AUTO", "MANUAL"] as const}
        value={app.account}
        onChange={app.setAccount}
        disabledValues={
          app.mode === "live"
            ? (["AUTO", "MANUAL"] as const).filter(
                (v) => !app.sessionInfo?.accounts.includes(v),
              )
            : []
        }
      />
      <Button
        title="Performansı yenile"
        variant="ghost"
        disabled={q.loading}
        onPress={q.reload}
      />
      {q.stale && p ? (
        <Label muted>
          Güncel değil · son hesap sorgusu:{" "}
          {q.loadedAt
            ? new Date(q.loadedAt).toLocaleString("tr-TR")
            : "Zaman yok"}
        </Label>
      ) : null}
      {q.error ? <Failure message={q.error} retry={q.reload} /> : null}
      {q.loading && !p ? (
        <Loading />
      ) : !p && !q.error ? (
        <Empty text="Bu hesap için doğrulanmış performans kaydı yok." />
      ) : p ? (
        <Card>
          <Heading>{String(p.portfolio_id)}</Heading>
          <Row name="Kapanan pozisyon" value={String(p.closed_positions)} />
          <Row
            name="Kazanç / Kayıp adedi"
            value={String(p.wins) + " / " + String(p.losses)}
          />
          <Row
            name="Belirsiz pozisyonlar"
            value={String(p.ambiguous_positions ?? "—")}
          />
          <Row
            name="Kazanma oranı"
            value={
              p.win_rate == null
                ? "Tanımsız · örnek yok"
                : String(p.win_rate) + "%"
            }
          />
          <Row
            name="Gerçekleşen sanal PnL"
            value={money(String(p.realized_pnl_quote)) + " USDT"}
          />
          <Row name="Masraflar" value={money(String(p.fees_quote)) + " USDT"} />
        </Card>
      ) : null}
      {app.mode === "live" && app.uiMode !== "basic" ? (
        <>
          <Button
            title={
              loadGraph
                ? "PnL kayıtlarını yenile"
                : "Gerçekleşen PnL kayıtlarını yükle"
            }
            secondary
            disabled={graph.loading}
            onPress={() => {
              if (loadGraph) graph.reload();
              else setLoadGraph(true);
            }}
          />
          {loadGraph ? (
            graph.loading ? (
              <Loading />
            ) : graph.error ? (
              <Failure message={graph.error} retry={graph.reload} />
            ) : graph.data && graph.data.length >= 2 ? (
              <Card>
                <Heading>Yüklenen işlemlerin PnL toplamı</Heading>
                <MiniPriceChart
                  prices={graph.data.map((v) => v.value)}
                  accessibilityLabel="Yüklenen gerçek sanal defter işlemlerinin birikimli PnL grafiği"
                />
                <Row
                  name="Bu pencerenin toplamı"
                  value={
                    money(graph.data[graph.data.length - 1].value) + " USDT"
                  }
                />
                <Label muted>
                  {new Date(graph.data[0].time).toLocaleString("tr-TR")} →{" "}
                  {new Date(
                    graph.data[graph.data.length - 1].time,
                  ).toLocaleString("tr-TR")}
                </Label>
                <Label muted>
                  Son yüklenen en çok 20 defter işlemi. Toplama ilk yüklenen
                  işlemden başlar; tüm hesap özsermayesi/getirisi veya backtest
                  grafiği değildir.
                </Label>
              </Card>
            ) : (
              <Empty text="PnL grafiği için aynı hesapta en az iki gerçek defter kaydı gerekir. Örnek eğri üretilmedi." />
            )
          ) : null}
        </>
      ) : null}
      <EquityHistoryPanel />
      <Label muted>
        Belirsiz pozisyonlar kazanç sayılmaz. Bu sonuçlar istatistiksel başarı
        olasılığı veya backtest doğrulaması değildir.
      </Label>
    </Page>
  );
}
