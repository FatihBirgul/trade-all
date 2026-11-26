import React, { useState } from "react";
import { router } from "expo-router";
import { useBot } from "../src/bot/state";
import { useConfirm } from "../src/ui/confirm";
import { Button, Card, Field, IconBubble, Loading, Notice, Row, T } from "../src/ui/kit";
import { Sub, goBack } from "../src/ui/Sub";
import { c } from "../src/ui/theme";
import { View } from "react-native";

export default function Connection() {
  const bot = useBot();
  const confirm = useConfirm();
  const [origin, setOrigin] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function connect() {
    setBusy(true);
    setError("");
    try {
      // Adres çoğu zaman "https://" olmadan kopyalanır; yalnızca güvenli (https) bağlantı kurulur.
      const address = origin.trim();
      await bot.pair(/^[a-z]+:\/\//i.test(address) ? address : "https://" + address, code.trim());
      setCode("");
      goBack(); // eşleşme bitti: kullanıcı bu ekranda kalmaz, Panel'e döner
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Bağlantı kurulamadı.");
    } finally {
      setBusy(false);
    }
  }
  async function disconnect() {
    if (await confirm({ title: "Bağlantı silinsin mi?", message: "Bu telefon bottan ayrılır. Bot çalışmaya devam eder; yeniden bağlanmak için sunucuda yeni kod üretmeniz gerekir.", confirm: "Bağlantıyı sil", danger: true }))
      await bot.disconnect();
  }

  return (
    <Sub title="Bağlantı" testID="screen-connection">
      {bot.phase === "loading" ? (
        <Loading label="Bağlantı bilgisi okunuyor…" />
      ) : bot.phase === "ready" && bot.config ? (
        <>
          <Card testID="connected-card">
            <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
              <IconBubble icon="checkmark" color={c.up} bg={c.upSoft} />
              <View style={{ flex: 1 }}>
                <T weight="800" size={18}>Bağlı</T>
                <T muted size={13}>{bot.config.origin.replace("https://", "")}</T>
              </View>
            </View>
            <Row name="Eşleştirme" value={new Date(bot.config.pairedAt).toLocaleString("tr-TR")} />
            <Row name="Son yanıt" value={bot.lastOkAt ? new Date(bot.lastOkAt).toLocaleTimeString("tr-TR") : "henüz yok"} />
            {bot.error ? <Notice kind="bad" text={bot.error} /> : null}
            <Button testID="to-panel" title="Panele git" icon="grid" onPress={goBack} />
            <Button title="İstek günlüğü (tanı)" kind="tonal" icon="pulse" onPress={() => router.push("/diagnostics")} />
          </Card>
          <Button testID="disconnect" title="Bağlantıyı sil" kind="dangerText" onPress={() => void disconnect()} />
        </>
      ) : (
        <Card testID="pair-card">
          <T weight="800" size={18}>Sunucuya bağlan</T>
          {bot.phase === "revoked" ? <Notice kind="bad" text="Bu telefonun bağlantı anahtarı artık geçerli değil. Yeniden eşleştirin." /> : null}
          <T muted size={14}>Sunucuda <T weight="800" size={14}>sudo tradebot-pair</T> komutunu çalıştırın; verdiği adresi ve 6 haneli kodu buraya yazın. Kod 10 dakika geçerlidir.</T>
          <Field label="Sunucu adresi" placeholder="https://…sslip.io" value={origin} onChangeText={setOrigin} keyboardType="url" />
          <Field label="Eşleştirme kodu" placeholder="6 haneli kod" value={code} onChangeText={setCode} keyboardType="number-pad" maxLength={6} />
          {error ? <Notice testID="pair-error" kind="bad" text={error} /> : null}
          <Button testID="pair" title="Bağlan" icon="link" onPress={() => void connect()} busy={busy} disabled={!origin.trim() || code.trim().length !== 6} />
        </Card>
      )}
    </Sub>
  );
}
