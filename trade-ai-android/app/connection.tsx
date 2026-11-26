import React, { useState } from "react";
import { Alert } from "react-native";
import { router } from "expo-router";
import { BotInput, BotPage } from "../src/bot/BotPage";
import { useBot } from "../src/bot/state";
import { useTheme } from "../src/theme";
import { Button, Card, Heading, Label, Row, ScreenHeader } from "../src/ui";

export default function Connection() {
  const bot = useBot();
  const theme = useTheme();
  const [origin, setOrigin] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Bu ekran sekmelerin üstünde açılır ve sekme çubuğu yoktur; eşleşme sonrası kullanıcı burada kalmamalı.
  function openPanel() {
    if (router.canGoBack()) router.back();
    else router.replace("/");
  }
  async function connect() {
    setBusy(true);
    setError("");
    try {
      // Adres çoğu zaman "https://" olmadan kopyalanır; yalnızca güvenli (https) bağlantı kurulur.
      const address = origin.trim();
      await bot.pair(/^[a-z]+:\/\//i.test(address) ? address : "https://" + address, code.trim());
      setCode("");
      openPanel();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Bağlantı kurulamadı.");
    } finally {
      setBusy(false);
    }
  }
  function confirmDisconnect() {
    Alert.alert(
      "Bağlantı silinsin mi?",
      "Bu telefon bottan ayrılır. Bot çalışmaya devam eder; yeniden bağlanmak için sunucuda yeni kod üretmeniz gerekir.",
      [
        { text: "Vazgeç", style: "cancel" },
        { text: "Bağlantıyı sil", style: "destructive", onPress: () => void bot.disconnect() },
      ],
    );
  }

  return (
    <BotPage>
      <ScreenHeader title="Bağlantı" badge="TRADE BOT" />
      {bot.phase === "ready" && bot.config ? (
        <Card>
          <Heading>Bağlı</Heading>
          <Row name="Sunucu" value={bot.config.origin.replace("https://", "")} />
          <Row name="Eşleştirme" value={new Date(bot.config.pairedAt).toLocaleString("tr-TR")} />
          <Row
            name="Son yanıt"
            value={bot.lastOkAt ? new Date(bot.lastOkAt).toLocaleTimeString("tr-TR") : "henüz yok"}
          />
          {bot.error ? <Label style={{ color: theme.colors.red }}>{bot.error}</Label> : null}
          <Button title="Panele git" onPress={openPanel} />
          <Button title="Bağlantıyı sil" onPress={confirmDisconnect} secondary />
        </Card>
      ) : bot.phase === "loading" ? null : (
        <Card>
          <Heading>Sunucuya bağlan</Heading>
          {bot.phase === "revoked" ? (
            <Label style={{ color: theme.colors.red }}>
              Bu telefonun bağlantı anahtarı artık geçerli değil. Yeniden eşleştirin.
            </Label>
          ) : null}
          <BotInput
            accessibilityLabel="Sunucu adresi"
            placeholder="https://…sslip.io"
            keyboardType="url"
            editable={!busy}
            value={origin}
            onChangeText={setOrigin}
          />
          <BotInput
            accessibilityLabel="Eşleştirme kodu"
            placeholder="6 haneli kod"
            keyboardType="number-pad"
            maxLength={6}
            editable={!busy}
            value={code}
            onChangeText={setCode}
          />
          {error ? <Label style={{ color: theme.colors.red }}>{error}</Label> : null}
          <Button title={busy ? "Bağlanıyor…" : "Bağlan"} onPress={() => void connect()} disabled={busy} />
          <Label muted>
            Adres ve kod sunucuda üretilir: sunucuya bağlanıp “sudo tradebot-pair” yazın. Kod 10 dakika geçerlidir
            ve yalnızca bir kez kullanılabilir.
          </Label>
        </Card>
      )}
      <Card>
        <Heading>Görünüm</Heading>
        <Button title={theme.isDark ? "Açık temaya geç" : "Koyu temaya geç"} onPress={theme.toggle} secondary />
      </Card>
    </BotPage>
  );
}
