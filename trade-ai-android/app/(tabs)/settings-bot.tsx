import React, { useState } from "react";
import { Alert, Switch, View } from "react-native";
import { router } from "expo-router";
import { BotInput, BotPage, Disconnected } from "../../src/bot/BotPage";
import { MODE_LABEL, NUMBER_FIELDS, draftFrom, planChanges, strategyName, type Draft } from "../../src/bot/settingsForm";
import { useBot } from "../../src/bot/state";
import { useResource } from "../../src/resource";
import type { BotSettings, BotStrategy, StrategyMode } from "../../src/bot/types";
import { useTheme } from "../../src/theme";
import { Button, Card, Failure, Heading, Label, Loading, ScreenHeader } from "../../src/ui";

export default function SettingsBot() {
  const bot = useBot();
  const { colors } = useTheme();
  const [edited, setEdited] = useState<{ base: BotSettings; draft: Draft } | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ text: string; bad: boolean } | null>(null);
  const ready = bot.phase === "ready";
  const api = bot.api;
  const query = useResource(() => Promise.all([api.settings(), api.strategies()]), "settings:" + (bot.config?.origin ?? ""));
  const settings: BotSettings | null = query.data?.[0] ?? null;
  const strategies: BotStrategy[] = query.data?.[1] ?? [];
  const error = query.error ?? "";
  const load = query.reload;
  // Sunucudan yeni ayar gelince form o değerlere döner; kullanıcının yazdığı taslak yalnızca aynı kopya içindir.
  const draft: Draft | null = settings ? (edited && edited.base === settings ? edited.draft : draftFrom(settings)) : null;
  const setDraft = (next: Draft) => {
    if (settings) setEdited({ base: settings, draft: next });
  };

  async function run(action: () => Promise<unknown>, done: string) {
    if (busy) return;
    setBusy(true);
    setNotice(null);
    try {
      await action();
      setNotice({ text: done, bad: false });
    } catch (reason) {
      setNotice({ text: reason instanceof Error ? reason.message : "İşlem tamamlanamadı.", bad: true });
    } finally {
      setBusy(false);
      load(); // sunucudaki gerçek değerler yeniden gösterilir
    }
  }
  function save() {
    if (!settings || !draft) return;
    const plan = planChanges(settings, draft);
    if (!plan.ok) return setNotice({ text: plan.error, bad: true });
    if (plan.changes.length === 0) return setNotice({ text: "Değişiklik yok.", bad: false });
    const lines = plan.changes.map((c) => c.label + ": " + c.from + " → " + c.to + (c.riskier ? "  ⚠ risk artar" : ""));
    Alert.alert(
      plan.riskier ? "Dikkat: risk artıyor" : "Ayarlar kaydedilsin mi?",
      lines.join("\n") + (plan.riskier ? "\n\nİşaretli değişiklikler kaybedebileceğiniz tutarı büyütür." : ""),
      [
        { text: "Vazgeç", style: "cancel" },
        {
          text: plan.riskier ? "Riski artır ve kaydet" : "Kaydet",
          style: plan.riskier ? "destructive" : "default",
          onPress: () => void run(() => api.updateSettings(plan.apply), "Ayarlar kaydedildi."),
        },
      ],
    );
  }
  function changeMode(strategy: BotStrategy, mode: StrategyMode) {
    const name = strategyName(strategy.strategy_id);
    if (mode !== "live") {
      Alert.alert(name, mode === "off" ? "Strateji kapatılsın mı? Sinyalleri izlenmez." : "Strateji gölgeye alınsın mı? Sinyalleri izlenir, emir gönderilmez.", [
        { text: "Vazgeç", style: "cancel" },
        { text: MODE_LABEL[mode] + " yap", onPress: () => void run(() => api.setStrategyMode(strategy.strategy_id, mode), name + ": " + MODE_LABEL[mode]) },
      ]);
      return;
    }
    Alert.alert(
      name + " canlıya alınsın mı?",
      "Bu strateji GERÇEK PARA ile işlem açmaya başlar." +
        (strategy.shadow.trades ? "\n\nGölge karnesi: " + strategy.shadow.trades + " işlem." : ""),
      [
        { text: "Vazgeç", style: "cancel" },
        {
          text: "Canlıya al",
          style: "destructive",
          onPress: () => void run(() => api.setStrategyMode(strategy.strategy_id, "live", true), name + ": Canlı"),
        },
      ],
    );
  }

  return (
    <BotPage>
      <ScreenHeader title="Ayarlar" badge="TRADE BOT" />
      <Disconnected />
      {ready ? (
        <>
          {error ? <Failure message={"Ayarlar alınamadı. " + error} retry={load} /> : null}
          {!settings || !draft ? (
            error ? null : <Loading />
          ) : (
            <>
              <Card>
                <Heading>Risk ve sınırlar</Heading>
                {NUMBER_FIELDS.map((field) => (
                  <View key={field.key} style={{ gap: 4 }}>
                    <Label muted style={{ fontSize: 12 }}>
                      {field.label} ({String(field.min).replace(".", ",")}–{String(field.max).replace(".", ",")}{field.unit})
                    </Label>
                    <BotInput
                      accessibilityLabel={field.label}
                      keyboardType="decimal-pad"
                      editable={!busy}
                      value={draft[field.key] as string}
                      onChangeText={(value) => setDraft({ ...draft, [field.key]: value })}
                    />
                  </View>
                ))}
                {(
                  [
                    ["news_enabled", "Haber penceresi koruması"],
                    ["fusion_enabled", "Güven puanı"],
                  ] as const
                ).map(([key, label]) => (
                  <View key={key} style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", minHeight: 48 }}>
                    <Label>{label}</Label>
                    <Switch accessibilityLabel={label} value={draft[key]} disabled={busy} onValueChange={(value) => setDraft({ ...draft, [key]: value })} />
                  </View>
                ))}
                <Button title="Kaydet" onPress={save} disabled={busy} />
                <Label muted style={{ fontSize: 12 }}>
                  Deneme/canlı kipi Panel’den, strateji kipleri aşağıdan değiştirilir; ikisi de ayrı onay ister.
                </Label>
              </Card>
              <Card>
                <Heading>Stratejiler</Heading>
                {strategies.map((strategy) => (
                  <View key={strategy.strategy_id} style={{ gap: 6, paddingVertical: 4 }}>
                    <Label style={{ fontWeight: "700" }}>
                      {strategyName(strategy.strategy_id)} · {MODE_LABEL[strategy.mode]}
                      {strategy.paused ? " (bot duraklattı)" : ""}
                    </Label>
                    {strategy.mode !== "live" && strategy.live_blocker ? (
                      <Label muted style={{ fontSize: 12 }}>{strategy.live_blocker}</Label>
                    ) : null}
                    <View style={{ flexDirection: "row", gap: 6, flexWrap: "wrap" }}>
                      {strategy.mode !== "live" ? (
                        <Button
                          title="Canlıya al"
                          accessibilityLabel={"Canlıya al " + strategy.strategy_id}
                          onPress={() => changeMode(strategy, "live")}
                          disabled={busy || !strategy.can_go_live}
                          secondary
                        />
                      ) : null}
                      {strategy.mode !== "shadow" ? (
                        <Button title="Gölge" accessibilityLabel={"Gölge " + strategy.strategy_id} onPress={() => changeMode(strategy, "shadow")} disabled={busy} secondary />
                      ) : null}
                      {strategy.mode !== "off" ? (
                        <Button title="Kapat" accessibilityLabel={"Kapat " + strategy.strategy_id} onPress={() => changeMode(strategy, "off")} disabled={busy} secondary />
                      ) : null}
                    </View>
                  </View>
                ))}
              </Card>
            </>
          )}
          {notice ? <Label style={{ color: notice.bad ? colors.red : colors.muted }}>{notice.text}</Label> : null}
        </>
      ) : null}
      <Card>
        <Heading>Bağlantı ve görünüm</Heading>
        <Button title="Bağlantı ayarları" onPress={() => router.push("/connection")} secondary />
      </Card>
    </BotPage>
  );
}
