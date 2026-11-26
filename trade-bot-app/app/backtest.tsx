import React, { useState } from "react";
import { Pressable, View } from "react-native";
import { priceText, rText, timeText } from "../src/bot/presentation";
import { strategyName } from "../src/bot/settingsForm";
import { useBot } from "../src/bot/state";
import type { BacktestStrategy, BacktestWindow, BacktestWindowKey } from "../src/bot/types";
import { Button, Card, Empty, Failure, Loading, Notice, Pill, Row, Segmented, T } from "../src/ui/kit";
import { Sub } from "../src/ui/Sub";
import { c, tone } from "../src/ui/theme";
import { useResource } from "../src/ui/useResource";

// Backtest: sunucunun geçmiş Exness mumlarıyla yaptığı ölçüm (1 ay / 6 ay / 1 yıl). Benzetimdir; gerçek işlem değil.
const WINDOWS = [["1m", "1A"], ["6m", "6A"], ["1y", "1Y"]] as const;
const WINDOW_NAME: Record<BacktestWindowKey, string> = { "1m": "Son 1 ay", "6m": "Son 6 ay", "1y": "Son 1 yıl" };
const num = (value: number | null | undefined, digits = 2) =>
  value == null || !Number.isFinite(value) ? "—" : priceText(Math.round(value * 10 ** digits) / 10 ** digits);
const pct = (value: number | null | undefined) => (value == null ? "—" : "%" + num(Math.abs(value), 1));
const usc = (value: number) => (value > 0 ? "+" : value < 0 ? "−" : "") + num(Math.abs(value), 0) + " USC";
const dateText = (epoch: number) => {
  const d = new Date(epoch * 1000);
  return String(d.getUTCDate()).padStart(2, "0") + "." + String(d.getUTCMonth() + 1).padStart(2, "0") + "." + d.getUTCFullYear();
};

function Badge({ row }: { row: BacktestStrategy }) {
  const passed = row.verdict.passed;
  if (passed === true) return <Pill label="Geçti" color={c.up} bg={c.upSoft} />;
  if (passed === false) return <Pill label="Kaldı" color={c.down} bg={c.downSoft} />;
  return <Pill label="Bekliyor" color={c.sun} bg={c.sunSoft} />;
}

// Bakiye eğrisi: noktalar eşit aralıklı sütunlar olarak çizilir (başlangıç bakiyesi taban çizgisidir).
function Curve({ window }: { window: BacktestWindow }) {
  const points = window.curve ?? [];
  if (points.length < 2) return <T muted size={13}>Bu pencerede kapanmış işlem yok.</T>;
  const values = points.map((point) => point[1]);
  const low = Math.min(...values);
  const high = Math.max(...values);
  const span = high - low || 1;
  const start = values[0];
  return (
    <View testID="backtest-curve" style={{ gap: 6 }}>
      <View style={{ height: 96, flexDirection: "row", alignItems: "flex-end", gap: 1 }}>
        {values.map((value, index) => (
          <View key={index} style={{ flex: 1, height: 4 + ((value - low) / span) * 92, borderRadius: 2, backgroundColor: value >= start ? c.up : c.down }} />
        ))}
      </View>
      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
        <T muted size={12}>{dateText(points[0][0])} · {num(start, 0)} USC</T>
        <T muted size={12}>{dateText(points[points.length - 1][0])} · {num(values[values.length - 1], 0)} USC</T>
      </View>
      <T muted size={12}>En düşük {num(low, 0)} · en yüksek {num(high, 0)} USC</T>
    </View>
  );
}

function Detail({ row, window, windowKey }: { row: BacktestStrategy; window: BacktestWindow; windowKey: BacktestWindowKey }) {
  const symbols = Object.entries(window.by_symbol ?? {}).sort((a, b) => b[1].net_r - a[1].net_r);
  return (
    <View testID="backtest-detail" style={{ gap: 10, borderTopWidth: 1, borderTopColor: c.line, paddingTop: 12 }}>
      <Row name="Net sonuç" value={rText(window.net_r) + " · " + usc(window.net_usc)} color={tone(window.net_r)} />
      <Row name="İşlem (kapanan / açık)" value={window.closed + " / " + window.open} />
      <Row name="Kazanma" value={pct(window.win_pct) + " (" + window.wins + "/" + window.closed + ")"} />
      <Row name="Kâr faktörü (PF)" value={num(window.pf)} />
      <Row name="En büyük düşüş" value={rText(window.max_dd_r) + " · " + pct(window.max_dd_pct)} />
      <Row name="Maliyet ÷ stop (medyan)" value={pct(window.cost_stop_pct)} />
      <Row name="1 yıl: ilk 6 ay / son 6 ay" value={rText(row.halves.first.net_r) + " / " + rText(row.halves.second.net_r)} />
      <Row name="Maliyet kapısına takılan sinyal" value={row.cost_gate.blocked + " / " + row.cost_gate.signals} />
      <Row name="Portföy sınırına takılan" value={String(row.portfolio_rejected)} />
      {row.verdict.reasons.length ? (
        <View style={{ gap: 4 }}>
          <T weight="800" size={14}>{row.verdict.passed === null ? "Neden bekliyor / eksikler" : "Neden kaldı"}</T>
          {row.verdict.reasons.map((reason) => (<T key={reason} muted size={13}>• {reason}</T>))}
        </View>
      ) : null}
      <T weight="800" size={14}>Bakiye eğrisi · {WINDOW_NAME[windowKey]}</T>
      <Curve window={window} />
      <T weight="800" size={14}>Sembole göre · {WINDOW_NAME[windowKey]}</T>
      {symbols.length === 0 ? (
        <T muted size={13}>Bu pencerede kapanmış işlem yok.</T>
      ) : (
        <View testID="backtest-symbols" style={{ gap: 6 }}>
          {symbols.map(([symbol, item]) => (
            <View key={symbol} style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
              <T weight="700" size={14} style={{ width: 84 }}>{symbol}</T>
              <T muted size={13} style={{ flex: 1 }}>{item.trades} işlem · {item.wins} kazanç</T>
              <T weight="800" size={14} style={{ color: tone(item.net_r) }}>{rText(item.net_r) || "0R"}</T>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

function StrategyCard({ id, title, row, windowKey, open, toggle }: { id: string; title: string; row: BacktestStrategy; windowKey: BacktestWindowKey; open: boolean; toggle: () => void }) {
  const window = row.windows[windowKey];
  return (
    <Card testID={"backtest-" + id}>
      <Pressable accessibilityRole="button" accessibilityLabel={title + " ayrıntısı"} onPress={toggle} style={{ gap: 8 }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <T weight="800" size={16} style={{ flex: 1 }}>{title}</T>
          <Badge row={row} />
        </View>
        <View style={{ flexDirection: "row", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
          <T weight="900" size={24} style={{ color: tone(window.net_r) }}>{rText(window.net_r) || "0R"}</T>
          <T weight="700" size={15} style={{ color: tone(window.net_usc) }}>{usc(window.net_usc)}</T>
        </View>
        <T muted size={13}>
          {window.closed} işlem · kazanma {pct(window.win_pct)} · PF {num(window.pf)} · düşüş {pct(window.max_dd_pct)} · maliyet/stop {pct(window.cost_stop_pct)}
        </T>
        {!window.complete ? <T size={13} style={{ color: c.sun }}>Bu pencerenin verisi henüz tam değil; rakamlar eldeki kısımdan.</T> : null}
        <T muted size={12}>{open ? "Ayrıntıyı gizle" : "Sembol tablosu ve bakiye eğrisi için dokunun"}</T>
      </Pressable>
      {open ? <Detail row={row} window={window} windowKey={windowKey} /> : null}
    </Card>
  );
}

export default function Backtest() {
  const bot = useBot();
  const [windowKey, setWindowKey] = useState<BacktestWindowKey>("1y");
  const [openId, setOpenId] = useState<string | null>(null);
  const ready = bot.phase === "ready";
  const report = useResource(ready ? () => bot.api.backtest() : null, "backtest:" + bot.config?.origin);
  const result = report.data?.result ?? null;
  const rank = (row: BacktestStrategy) => (row.verdict.passed === true ? 0 : row.verdict.passed === null ? 1 : 2);
  const rows = result
    ? Object.entries(result.strategies).sort((a, b) => rank(a[1]) - rank(b[1]) || b[1].windows[windowKey].net_r - a[1].windows[windowKey].net_r)
    : [];
  const passed = rows.filter(([, row]) => row.verdict.passed === true).length;

  return (
    <Sub title="Backtest" testID="screen-backtest">
      {!ready ? (
        <Empty icon="link" title="Sunucuya bağlı değilsiniz" text="Backtest sonuçlarını görmek için telefonu sunucuyla eşleştirin." />
      ) : !report.data ? (
        report.error ? <Failure message={report.error} retry={() => void report.reload()} /> : <Loading label="Backtest sonuçları yükleniyor…" />
      ) : !result ? (
        <Empty icon="hourglass" title="Henüz sonuç yok" text={"Sunucu geçmiş mumları indirip hesaplıyor (durum: " + report.data.state + "). İlk sonuçlar hazır olunca burada görünür."}>
          <Button title="Yenile" kind="tonal" icon="refresh" onPress={() => void report.reload()} busy={report.loading} />
        </Empty>
      ) : (
        <>
          {report.error ? <Notice text={"Sonuç yenilenemedi: " + report.error} /> : null}
          <Card testID="backtest-summary">
            <T muted size={14}>Geçmiş Exness mumlarıyla ölçüm · benzetim</T>
            <T weight="900" size={22}>{passed} / {rows.length} strateji geçti</T>
            <Row name="Sonuç tarihi" value={timeText(result.finished_at)} />
            <Row name="Dönem" value={dateText(result.from) + " – " + dateText(result.to)} />
            <Row name="Veri kapsamı (sembol medyanı)" value={num(result.history.days_median, 0) + " gün · " + result.symbols + " sembol"} />
            <Row name="Durum" value={result.complete ? "Tamamlandı" : "Sürüyor · V9: son " + num(result.progress.v9_days_complete, 0) + " gün hazır"} color={result.complete ? c.up : c.sun} />
            <T muted size={13}>
              Başlangıç {num(result.rules.start_balance, 0)} USC, işlem başına %{num(result.rules.risk_pct, 1)} risk · en çok {result.rules.max_open} açık işlem · maliyet kapısı {result.rules.max_spread_stop_pct == null ? "—" : "%" + num(result.rules.max_spread_stop_pct, 0)} · swap {result.rules.swap}
              {result.rules.news_applied ? "" : " · haber penceresi geçmişe uygulanamadı"}
            </T>
            <T muted size={13}>
              Geçme ölçütü: 1 yılda en az {result.pass_rule.min_trades} işlem, PF en az {num(result.pass_rule.min_pf, 1)}, iki yarıyıl da artı, düşüş en çok %{num(result.pass_rule.max_dd_pct, 0)}, 6 ay da artı.
            </T>
          </Card>
          <Segmented options={WINDOWS} value={windowKey} onChange={setWindowKey} />
          {result.combined ? (
            <StrategyCard id="combined" title={"Geçenlerin birleşik portföyü (" + (result.combined.strategies?.length ?? 0) + ")"} row={result.combined} windowKey={windowKey} open={openId === "combined"} toggle={() => setOpenId(openId === "combined" ? null : "combined")} />
          ) : (
            <Notice testID="backtest-none-passed" kind="info" text="Geçme ölçütünü sağlayan strateji olmadığı için birleşik portföy satırı yok." />
          )}
          {rows.map(([id, row]) => (
            <StrategyCard key={id} id={id} title={strategyName(id)} row={row} windowKey={windowKey} open={openId === id} toggle={() => setOpenId(openId === id ? null : id)} />
          ))}
          <Button title="Yenile" kind="tonal" icon="refresh" onPress={() => void report.reload()} busy={report.loading} />
        </>
      )}
    </Sub>
  );
}
