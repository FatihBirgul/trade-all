import React, { useState } from "react";
import { Pressable, TextInput, View } from "react-native";
import { router } from "expo-router";
import appConfig from "../../app.json";
import { priceText } from "../../src/bot/presentation";
import { MODE_LABEL, NUMBER_FIELDS, TOGGLES, draftFrom, planChanges, strategyName, type Draft } from "../../src/bot/settingsForm";
import { useBot } from "../../src/bot/state";
import type { BotSettings, BotStrategy, StrategyMode } from "../../src/bot/types";
import { useConfirm } from "../../src/ui/confirm";
import { DataGate } from "../../src/ui/DataGate";
import { Button, Card, Failure, Loading, Notice, Pill, Screen, T, Toggle } from "../../src/ui/kit";
import { c } from "../../src/ui/theme";
import { useResource } from "../../src/ui/useResource";

const TOGGLE_HINT: Record<string, string> = {
  news_enabled: "Önemli haberlerin çevresinde yeni işlem açılmaz.",
  fusion_enabled: "Düşük puanlı sinyaller açılmaz, orta puanlılar yarım lotla açılır.",
  be_enabled: "Kâr 1R olunca stop girişe çekilir.",
  partial_enabled: "Kâr 2R olunca pozisyonun yarısı kapatılır.",
  trail_enabled: "Sonrasında stop fiyatı izler.",
};
const MODES: StrategyMode[] = ["live", "shadow", "off"];

export default function Settings() {
  const bot = useBot();
  const confirm = useConfirm();
  const api = bot.api;
  const ready = bot.phase === "ready";
  const query = useResource(ready ? () => Promise.all([api.settings(), api.strategies(), api.symbols()]) : null, "settings:" + bot.config?.origin);
  const [edits, setEdits] = useState<Partial<Draft>>({});
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ text: string; bad: boolean; where: "settings" | "strategies" } | null>(null);
  const settings: BotSettings | null = query.data?.[0] ?? null;
  const strategies: BotStrategy[] = query.data?.[1] ?? [];
  const universe: string[] = (query.data?.[2] ?? []).map((row) => row.symbol);
  const draft: Draft | null = settings ? { ...draftFrom(settings), ...edits } : null;
  const setField = (change: Partial<Draft>) => setEdits((old) => ({ ...old, ...change }));
  // Son okuma başarısızsa ekrandaki ayarlar eski olabilir: eski → yeni karşılaştırması yanıltmasın diye kayıt kapalıdır.
  const outdated = Boolean(query.error) || query.loading;
  const dirty = Object.keys(edits).length > 0;

  async function run(action: () => Promise<unknown>, done: string, saved = false, where: "settings" | "strategies" = "settings") {
    if (busy) return;
    setBusy(true);
    setNotice(null);
    try {
      await action();
      if (saved) setEdits({});
      setNotice({ text: done, bad: false, where });
    } catch (reason) {
      setNotice({ text: reason instanceof Error ? reason.message : "İşlem tamamlanamadı.", bad: true, where });
    } finally {
      setBusy(false);
      void query.reload(); // sunucudaki gerçek değerler yeniden gösterilir
    }
  }
  async function save() {
    if (!settings || !draft) return;
    if (outdated) return setNotice({ text: "Ayarlar güncel değil; önce yeniden yükleyin.", bad: true, where: "settings" });
    const plan = planChanges(settings, draft, universe);
    if (!plan.ok) return setNotice({ text: plan.error, bad: true, where: "settings" });
    if (plan.changes.length === 0) return setNotice({ text: "Değişiklik yok.", bad: false, where: "settings" });
    const lines = plan.changes.map((change) => change.label + ": " + change.from + " → " + change.to + (change.riskier ? "  ⚠ risk artar" : ""));
    const ok = await confirm({
      title: plan.riskier ? "Dikkat: risk artıyor" : "Ayarlar kaydedilsin mi?",
      message: lines.join("\n") + (plan.riskier ? "\n\nİşaretli değişiklikler kaybedebileceğiniz tutarı büyütür." : ""),
      confirm: plan.riskier ? "Riski artır ve kaydet" : "Kaydet",
      danger: plan.riskier,
    });
    if (ok) await run(() => api.updateSettings(plan.apply), "Ayarlar kaydedildi.", true);
  }
  async function changeMode(strategy: BotStrategy, mode: StrategyMode) {
    const name = strategyName(strategy.strategy_id);
    if (mode !== "live") {
      if (await confirm({ title: name, message: mode === "off" ? "Strateji kapatılsın mı? Sinyalleri izlenmez." : "Strateji gölgeye alınsın mı? Sinyalleri izlenir, emir gönderilmez.", confirm: MODE_LABEL[mode] + " yap" }))
        await run(() => api.setStrategyMode(strategy.strategy_id, mode), name + ": " + MODE_LABEL[mode], false, "strategies");
      return;
    }
    const shadow = strategy.shadow;
    const dryRun = bot.status?.dry_run !== false;
    const message =
      (dryRun ? "Bot şu an DENEME modunda: strateji canlı işaretlenir, bot canlı moda geçtiğinde GERÇEK PARA ile işlem açar." : "Bu strateji GERÇEK PARA ile işlem açmaya başlar.") +
      (shadow.trades ? "\n\nGölge karnesi: " + shadow.trades + " işlem" + (shadow.win_rate != null ? ", kazanma %" + Math.round(shadow.win_rate * 100) : "") + (shadow.avg_r != null ? ", ortalama " + priceText(Number(shadow.avg_r.toFixed(2))) + " R" : "") + "." : "\n\nGölge karnesi yok.") +
      (shadow.avg_r != null && shadow.avg_r <= 0 ? "\n\n⚠ Gölge sonuçları ortalamada ZARARDA." : "") +
      (strategy.paused ? "\n\n⚠ Bot bu stratejiyi kötü sonuçlar nedeniyle duraklatmıştı; canlıya almak duraklatmayı kaldırır." : "");
    if (await confirm({ title: name + " canlıya alınsın mı?", message, confirm: "Canlıya al", danger: true }))
      await run(() => api.setStrategyMode(strategy.strategy_id, "live", true), name + ": Canlı", false, "strategies");
  }
  function toggleSymbol(symbol: string) {
    if (!draft) return;
    const current = draft.symbols ?? universe;
    const next = current.includes(symbol) ? current.filter((item) => item !== symbol) : [...current, symbol];
    setField({ symbols: next.length === universe.length ? null : next.sort() });
  }

  return (
    <Screen testID="screen-settings" title="Ayarlar">
      <DataGate>
        {!settings || !draft ? (
          query.error ? <Failure message={query.error} retry={() => void query.reload()} /> : <Loading label="Ayarlar yükleniyor…" />
        ) : (
          <>
            {query.error ? <Notice text={"Ayarlar yenilenemedi: " + query.error + " Kayıt kapalı."} /> : null}
            <Card testID="settings-risk">
              <T weight="800" size={16}>Risk ve sınırlar</T>
              {NUMBER_FIELDS.map((field) => (
                <View key={field.key} style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
                  <View style={{ flex: 1 }}>
                    <T weight="700" size={14}>{field.label}</T>
                    <T muted size={12}>{priceText(field.min)} – {priceText(field.max)}{field.unit}</T>
                  </View>
                  <TextInput accessibilityLabel={field.label} value={draft[field.key]} onChangeText={(value) => setField({ [field.key]: value })} keyboardType="decimal-pad" style={{ width: 92, minHeight: 46, borderRadius: 14, backgroundColor: c.bg, textAlign: "center", fontSize: 17, fontWeight: "800", color: c.text }} />
                </View>
              ))}
            </Card>
            <Card testID="settings-toggles">
              <T weight="800" size={16}>Korumalar ve stop aşamaları</T>
              {TOGGLES.map((toggle) => (
                <Toggle key={toggle.key} label={toggle.label} hint={TOGGLE_HINT[toggle.key]} value={draft[toggle.key]} onChange={(value) => setField({ [toggle.key]: value })} />
              ))}
              <T muted size={13}>Bir korumayı kapatmak riski artırır. Aşamalar kapansa da ilk stop Exness tarafında yerinde kalır.</T>
            </Card>
            <Card testID="settings-symbols">
              <View style={{ flexDirection: "row", alignItems: "center" }}>
                <T weight="800" size={16} style={{ flex: 1 }}>Botun işlem açabileceği semboller</T>
                <Pill label={(draft.symbols ?? universe).length + " / " + universe.length} />
              </View>
              <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
                {universe.map((symbol) => {
                  const on = (draft.symbols ?? universe).includes(symbol);
                  return (
                    <Pressable key={symbol} testID={"sym-" + symbol} accessibilityRole="switch" accessibilityLabel={symbol} accessibilityState={{ checked: on }} onPress={() => toggleSymbol(symbol)} style={{ backgroundColor: on ? c.hero : c.line, borderRadius: 14, paddingHorizontal: 12, paddingVertical: 9 }}>
                      <T weight="800" size={13} style={{ color: on ? c.white : c.muted }}>{symbol}</T>
                    </Pressable>
                  );
                })}
              </View>
              <View style={{ flexDirection: "row", gap: 10 }}>
                <Button title="Hepsini aç" kind="tonal" onPress={() => setField({ symbols: null })} style={{ flex: 1 }} />
                <Button title="Hepsini kapat" kind="tonal" onPress={() => setField({ symbols: [] })} style={{ flex: 1 }} />
              </View>
            </Card>
            {notice && notice.where === "settings" ? <Notice testID="settings-notice" kind={notice.bad ? "bad" : "info"} text={notice.text} /> : null}
            <Button testID="save-settings" title={dirty ? "Değişiklikleri kaydet" : "Kaydet"} icon="save" onPress={() => void save()} busy={busy} disabled={!dirty} />
            <Card testID="settings-strategies">
              <T weight="800" size={16}>Stratejiler</T>
              <T muted size={13}>Canlı: emir gönderir. Gölge: yalnızca izlenir. Yeni bir strateji, gölge karnesi yeterli olmadan canlıya alınamaz.</T>
              {notice && notice.where === "strategies" ? <Notice testID="strategy-notice" kind={notice.bad ? "bad" : "info"} text={notice.text} /> : null}
              {strategies.map((strategy) => (
                <View key={strategy.strategy_id} testID={"strategy-" + strategy.strategy_id} style={{ gap: 8, borderTopWidth: 1, borderTopColor: c.line, paddingTop: 12 }}>
                  <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
                    <T weight="800" style={{ flex: 1 }}>{strategyName(strategy.strategy_id)}</T>
                    {strategy.paused ? <Pill label="Duraklatıldı" color={c.down} bg={c.downSoft} /> : null}
                  </View>
                  <View style={{ flexDirection: "row", backgroundColor: c.line, borderRadius: 16, padding: 4 }}>
                    {MODES.map((mode) => {
                      const active = strategy.mode === mode;
                      const blocked = mode === "live" && !active && strategy.source === "custom" && !strategy.can_go_live;
                      return (
                        <Pressable key={mode} accessibilityRole="button" accessibilityLabel={MODE_LABEL[mode] + " " + strategy.strategy_id} accessibilityState={{ selected: active, disabled: blocked || busy }} disabled={active || blocked || busy} onPress={() => void changeMode(strategy, mode)} style={{ flex: 1, paddingVertical: 9, borderRadius: 12, alignItems: "center", backgroundColor: active ? (mode === "live" ? c.up : c.card) : "transparent", opacity: blocked ? 0.4 : 1 }}>
                          <T weight="800" size={13} style={{ color: active ? (mode === "live" ? c.white : c.hero) : c.muted }}>{MODE_LABEL[mode]}</T>
                        </Pressable>
                      );
                    })}
                  </View>
                  {strategy.live_blocker ? <T muted size={12}>Canlıya alınamaz: {strategy.live_blocker}</T> : null}
                </View>
              ))}
            </Card>
          </>
        )}
      </DataGate>
      <Card testID="settings-app">
        <T weight="800" size={16}>Uygulama</T>
        <Button testID="open-connection-settings" title="Bağlantı" kind="tonal" icon="link" onPress={() => router.push("/connection")} />
        <Button title="Tanı (istek günlüğü)" kind="tonal" icon="pulse" onPress={() => router.push("/diagnostics")} />
        <T muted size={12} style={{ textAlign: "center" }}>Trade Bot {appConfig.expo.version}</T>
      </Card>
    </Screen>
  );
}
