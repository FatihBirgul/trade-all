import React from "react";
import { View } from "react-native";
import { clockText } from "../src/bot/presentation";
import { clearRequests, useRequestLog } from "../src/bot/requestLog";
import { useBot } from "../src/bot/state";
import { Button, Card, Empty, Pill, Row, T } from "../src/ui/kit";
import { Sub } from "../src/ui/Sub";
import { c } from "../src/ui/theme";

// Tanı: uygulamanın sunucuya yaptığı son istekler. Bir ekran boş kalırsa nedenini burada görmek için.
export default function Diagnostics() {
  const bot = useBot();
  const log = useRequestLog();
  const failed = log.filter((entry) => entry.error).length;
  return (
    <Sub title="Tanı" testID="screen-diagnostics">
      <Card>
        <Row name="Bağlantı durumu" value={{ loading: "okunuyor", unconfigured: "eşleşmemiş", ready: "eşleşmiş", revoked: "iptal edilmiş" }[bot.phase]} />
        <Row name="Sunucu" value={bot.config ? bot.config.origin.replace("https://", "") : "—"} />
        <Row name="Son başarılı yanıt" value={bot.lastOkAt ? clockText(bot.lastOkAt) : "henüz yok"} />
        <Row name="Son hata" value={bot.error || "yok"} color={bot.error ? c.down : undefined} />
        <Row name="Kayıtlı istek / hatalı" value={log.length + " / " + failed} color={failed ? c.down : undefined} />
        <Button title="Şimdi yenile" kind="tonal" icon="refresh" onPress={() => void bot.refresh()} />
      </Card>
      {log.length === 0 ? (
        <Empty icon="pulse" title="Henüz istek yok" text="Uygulama sunucuya istek gönderdikçe burada listelenir." />
      ) : (
        <Card testID="request-log">
          <View style={{ flexDirection: "row", alignItems: "center" }}>
            <T weight="800" size={16} style={{ flex: 1 }}>Son istekler</T>
            <Button title="Temizle" kind="ghost" onPress={clearRequests} />
          </View>
          {log.map((entry, index) => (
            <View key={entry.at + ":" + index} style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
              <Pill label={entry.status ? String(entry.status) : "AĞ"} color={entry.error ? c.down : c.up} bg={entry.error ? c.downSoft : c.upSoft} />
              <View style={{ flex: 1 }}>
                <T weight="700" size={14}>{entry.method} {entry.path}</T>
                <T muted size={12}>{clockText(entry.at)} · {entry.ms} ms{entry.error ? " · " + entry.error : ""}</T>
              </View>
            </View>
          ))}
        </Card>
      )}
    </Sub>
  );
}
