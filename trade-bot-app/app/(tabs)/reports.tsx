import React, { useState } from "react";
import { View } from "react-native";
import { amountText, centNote, majorText, pnlText, priceText, timeText } from "../../src/bot/presentation";
import { MODE_LABEL, strategyName } from "../../src/bot/settingsForm";
import { useBot } from "../../src/bot/state";
import type { ReportPeriod, Totals } from "../../src/bot/types";
import { DataGate } from "../../src/ui/DataGate";
import { Button, Card, Empty, Failure, Loading, Notice, Pill, Row, Screen, Segmented, T } from "../../src/ui/kit";
import { c, soft, tone } from "../../src/ui/theme";
import { useResource } from "../../src/ui/useResource";

const PERIODS = [["day", "Gün"], ["week", "Hafta"], ["month", "Ay"]] as const;
const rate = (totals: Totals) => (totals.win_rate == null ? "—" : "%" + Math.round(totals.win_rate * 100) + " (" + totals.wins + "/" + totals.trades + ")");

export default function Reports() {
  const bot = useBot();
  const [period, setPeriod] = useState<ReportPeriod>("day");
  const ready = bot.phase === "ready";
  const report = useResource(ready ? () => bot.api.reports(period) : null, period + ":" + bot.config?.origin);
  const strategies = useResource(ready ? () => bot.api.strategies() : null, "strategies:" + bot.config?.origin);
  const currency = bot.status?.currency;
  const data = report.data;
  const rows = data ? data.periods.all.slice(-12).reverse() : [];
  const scale = Math.max(1, ...rows.map((row) => Math.abs(row.pnl)));

  return (
    <Screen testID="screen-reports" title="Raporlar" subtitle="Kapanan işlemler (UTC takvimi)">
      <DataGate>
        {!data ? (
          report.error ? <Failure message={report.error} retry={() => void report.reload()} /> : <Loading label="Rapor yükleniyor…" />
        ) : (
          <>
            {report.error ? <Notice text={"Rapor yenilenemedi: " + report.error} /> : null}
            <Card testID="report-totals">
              <T muted size={14}>Toplam kâr/zarar · tüm zamanlar</T>
              <T testID="report-pnl" weight="900" size={34} style={{ color: tone(data.totals.all.pnl) }}>{pnlText(data.totals.all.pnl, currency)}</T>
              {majorText(data.totals.all.pnl, currency, true) ? <T testID="report-major" weight="700" size={15}>{majorText(data.totals.all.pnl, currency, true)} · {centNote(currency)}</T> : null}
              <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
                <Pill label={data.totals.all.trades + " işlem"} />
                <Pill label={"Kazanma " + rate(data.totals.all)} />
              </View>
              <Row name="Bot" value={pnlText(data.totals.bot.pnl, currency) + " · " + data.totals.bot.trades + " işlem"} color={tone(data.totals.bot.pnl)} />
              <Row name="Elle" value={pnlText(data.totals.manual.pnl, currency) + " · " + data.totals.manual.trades + " işlem"} color={tone(data.totals.manual.pnl)} />
              <Row name="En büyük düşüş (bot / toplam)" value={amountText(data.max_drawdown.bot, currency) + " / " + amountText(data.max_drawdown.all, currency)} />
            </Card>
            {data.totals.all.trades === 0 ? (
              <Empty icon="pie-chart" title="Henüz kapanmış işlem yok" text={bot.status?.dry_run ? "Bot deneme modunda olduğu için gerçek işlem açılmıyor. Stratejilerin sanal (gölge) sonuçları aşağıda." : "İlk işlem kapandığında dönem dönem kâr/zarar burada görünür."} />
            ) : (
              <>
                <Card testID="report-periods">
                  <T weight="800" size={16}>Dönemlere göre</T>
                  <Segmented options={PERIODS} value={period} onChange={setPeriod} />
                  {rows.map((row) => (
                    <View key={row.period} style={{ gap: 5 }}>
                      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
                        <T muted size={14}>{row.period}</T>
                        <T weight="800" size={14} style={{ color: tone(row.pnl) }}>{pnlText(row.pnl, null)}</T>
                      </View>
                      <View style={{ height: 6, borderRadius: 3, backgroundColor: c.line }}>
                        <View style={{ height: 6, borderRadius: 3, width: `${Math.max(4, (Math.abs(row.pnl) / scale) * 100)}%`, backgroundColor: tone(row.pnl) }} />
                      </View>
                    </View>
                  ))}
                </Card>
                <Card testID="report-breakdown">
                  <T weight="800" size={16}>Stratejiye göre · tüm zamanlar</T>
                  {Object.entries(data.by_strategy).map(([id, row]) => (<Row key={id} name={strategyName(id) + " · " + row.wins + "/" + row.trades} value={pnlText(row.pnl, null)} color={tone(row.pnl)} />))}
                  <View style={{ height: 1, backgroundColor: c.line }} />
                  <T weight="800" size={16}>Sembole göre</T>
                  {Object.entries(data.by_symbol).map(([symbol, row]) => (<Row key={symbol} name={symbol + " · " + row.wins + "/" + row.trades} value={pnlText(row.pnl, null)} color={tone(row.pnl)} />))}
                </Card>
                <Card testID="report-history">
                  <T weight="800" size={16}>Son kapanan işlemler</T>
                  {data.history.slice(0, 20).map((trade) => (
                    <View key={trade.position_id} style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
                      <View style={{ flex: 1 }}>
                        <T weight="800">{trade.symbol} {trade.side === "BUY" ? "AL" : "SAT"} <T muted size={13}>· {trade.origin === "bot" ? "Bot" : "Elle"}</T></T>
                        <T muted size={13}>{priceText(trade.entry)} → {priceText(trade.close_price)}{trade.closed_at ? " · " + timeText(trade.closed_at) : ""}</T>
                      </View>
                      <Pill label={pnlText(trade.pnl, null)} color={tone(trade.pnl)} bg={soft(trade.pnl)} />
                    </View>
                  ))}
                </Card>
              </>
            )}
            <Card testID="report-shadow">
              <T weight="800" size={16}>Strateji karnesi (sanal işlemler)</T>
              <T muted size={13}>Gölge kipindeki stratejiler emir göndermez; sinyalleri sanal olarak izlenir.</T>
              {strategies.data ? (
                strategies.data.map((strategy) => (
                  <View key={strategy.strategy_id} style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
                    <View style={{ flex: 1 }}>
                      <T weight="700">{strategyName(strategy.strategy_id)}</T>
                      <T muted size={13}>{strategy.shadow.trades ? strategy.shadow.trades + " sanal işlem · kazanma %" + Math.round((strategy.shadow.win_rate ?? 0) * 100) + (strategy.shadow.avg_r == null ? "" : " · ortalama " + priceText(Math.round(strategy.shadow.avg_r * 100) / 100) + "R") : "henüz sanal işlem yok"}</T>
                    </View>
                    <Pill label={strategy.paused ? "Duraklatıldı" : MODE_LABEL[strategy.mode]} color={strategy.mode === "live" && !strategy.paused ? c.up : c.hero} bg={strategy.mode === "live" && !strategy.paused ? c.upSoft : c.tint} />
                  </View>
                ))
              ) : strategies.error ? (
                <T size={14}>Karne alınamadı: {strategies.error}</T>
              ) : (
                <T muted size={14}>Karne yükleniyor…</T>
              )}
            </Card>
            <Button title="Yenile" kind="tonal" icon="refresh" onPress={() => { void report.reload(); void strategies.reload(); }} busy={report.loading} />
          </>
        )}
      </DataGate>
    </Screen>
  );
}
