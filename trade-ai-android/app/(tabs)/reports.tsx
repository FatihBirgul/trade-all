import React, { useState } from "react";
import { BotPage, Disconnected } from "../../src/bot/BotPage";
import { amountText, pnlText, timeText } from "../../src/bot/presentation";
import { MODE_LABEL, strategyName } from "../../src/bot/settingsForm";
import { useBot } from "../../src/bot/state";
import { useResource } from "../../src/resource";
import type { BotReport, BotStrategy, Totals } from "../../src/bot/types";
import { Button, Card, Choices, Empty, Failure, Heading, Label, Loading, Row, ScreenHeader } from "../../src/ui";

const PERIODS = { Gün: "day", Hafta: "week", Ay: "month" } as const;
type PeriodLabel = keyof typeof PERIODS;

const rate = (totals: Totals) =>
  totals.win_rate == null ? "—" : "%" + Math.round(totals.win_rate * 100) + " (" + totals.wins + "/" + totals.trades + ")";
const rText = (value: number | null) =>
  value == null ? "—" : (value > 0 ? "+" : value < 0 ? "−" : "") + String(Math.abs(Number(value.toFixed(2)))).replace(".", ",") + "R";

export default function Reports() {
  const bot = useBot();
  const [label, setLabel] = useState<PeriodLabel>("Gün");
  const ready = bot.phase === "ready";
  const currency = bot.status?.currency;
  const api = bot.api;
  // Anahtar döneme bağlıdır: dönem değişince eski dönemin raporu yenisi gibi gösterilmez.
  const query = useResource(
    () => Promise.all([api.reports(PERIODS[label]), api.strategies()]),
    "reports:" + (bot.config?.origin ?? "") + ":" + label,
  );
  const report: BotReport | null = query.data?.[0] ?? null;
  const strategies: BotStrategy[] = query.data?.[1] ?? [];
  const loading = query.loading;
  const error = query.error ?? "";
  const load = query.reload;

  return (
    <BotPage>
      <ScreenHeader title="Raporlar" badge="TRADE BOT" />
      <Disconnected />
      {ready ? (
        <>
          <Choices values={Object.keys(PERIODS) as PeriodLabel[]} value={label} onChange={setLabel} />
          <Card>
            <Label muted style={{ fontSize: 12 }}>
              Son güncelleme: {query.loadedAt ? new Date(query.loadedAt).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" }) : "—"} · günler UTC saatine göre ayrılır
            </Label>
            <Button title="Yenile" onPress={load} disabled={loading} secondary />
          </Card>
          {loading && !report ? <Loading /> : null}
          {error ? <Failure message={"Rapor alınamadı. " + error} retry={load} /> : null}
          {report ? (
            <>
              <Card>
                <Heading>Kapanan işlemler (tümü)</Heading>
                {(["bot", "manual", "all"] as const).map((key) => (
                  <Row
                    key={key}
                    name={{ bot: "Bot", manual: "Elle", all: "Toplam" }[key]}
                    value={pnlText(report.totals[key].pnl, currency) + " · " + report.totals[key].trades + " işlem"}
                  />
                ))}
                <Row name="Bot kazanma oranı" value={rate(report.totals.bot)} />
                <Row name="Elle kazanma oranı" value={rate(report.totals.manual)} />
                <Row name="En büyük düşüş (bot)" value={amountText(report.max_drawdown.bot, currency)} />
                <Row name="En büyük düşüş (toplam)" value={amountText(report.max_drawdown.all, currency)} />
              </Card>
              <Card>
                <Heading>{label} bazında kâr/zarar</Heading>
                {report.periods.all.length === 0 ? (
                  <Label muted>Henüz kapanmış işlem yok.</Label>
                ) : (
                  report.periods.all.slice(-8).reverse().map((row) => (
                    <Row key={row.period} name={row.period} value={pnlText(row.pnl, currency)} />
                  ))
                )}
              </Card>
              <Card>
                <Heading>Stratejiler</Heading>
                {strategies.map((strategy) => {
                  const live = report.by_strategy[strategy.strategy_id];
                  return (
                    <Row
                      key={strategy.strategy_id}
                      name={strategyName(strategy.strategy_id) + " · " + MODE_LABEL[strategy.mode] + (strategy.paused ? " (duraklatıldı)" : "")}
                      value={
                        (live ? pnlText(live.pnl, currency) + " · " + live.wins + "/" + live.trades : "canlı işlem yok") +
                        (strategy.shadow.trades ? "\ngölge: " + strategy.shadow.trades + " işlem, ort. " + rText(strategy.shadow.avg_r) : "")
                      }
                    />
                  );
                })}
              </Card>
              <Card>
                <Heading>Semboller</Heading>
                {Object.keys(report.by_symbol).length === 0 ? (
                  <Label muted>Henüz kapanmış işlem yok.</Label>
                ) : (
                  Object.entries(report.by_symbol)
                    .sort((a, b) => Math.abs(b[1].pnl) - Math.abs(a[1].pnl))
                    .slice(0, 10)
                    .map(([symbol, row]) => (
                      <Row key={symbol} name={symbol} value={pnlText(row.pnl, currency) + " · " + row.wins + "/" + row.trades} />
                    ))
                )}
              </Card>
              <Heading>Son işlemler</Heading>
              {report.history.length === 0 ? (
                <Empty text="Henüz kapanmış işlem yok." />
              ) : (
                report.history.slice(0, 20).map((trade) => (
                  <Card key={trade.position_id}>
                    <Row
                      name={trade.symbol + " · " + (trade.side === "BUY" ? "AL" : "SAT") + " · " + (trade.origin === "bot" ? "Bot" : "Elle")}
                      value={pnlText(trade.pnl, currency)}
                    />
                    <Label muted style={{ fontSize: 12 }}>
                      {(trade.closed_at ? timeText(trade.closed_at) : "—") +
                        (trade.strategy_id ? " · " + strategyName(trade.strategy_id) : "")}
                    </Label>
                  </Card>
                ))
              )}
            </>
          ) : null}
        </>
      ) : null}
    </BotPage>
  );
}
