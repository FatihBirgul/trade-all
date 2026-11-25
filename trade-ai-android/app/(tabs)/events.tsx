import React, { useState } from "react";
import { View } from "react-native";
import { BotPage, Disconnected, StaleNotice } from "../../src/bot/BotPage";
import { isImportant, kindLabel } from "../../src/bot/notifications";
import { timeText } from "../../src/bot/presentation";
import { useBot } from "../../src/bot/state";
import { useTheme } from "../../src/theme";
import { Card, Choices, Empty, Label, Loading, ScreenHeader } from "../../src/ui";

const FILTERS = ["Önemli", "Tümü"] as const;

export default function Events() {
  const bot = useBot();
  const { colors } = useTheme();
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("Önemli");
  const ready = bot.phase === "ready";
  const shown = filter === "Tümü" ? bot.events : bot.events.filter(isImportant);
  return (
    <BotPage>
      <ScreenHeader title="Bildirimler" badge="TRADE BOT" />
      <Disconnected />
      {ready ? (
        <>
          <StaleNotice />
          <Choices values={FILTERS} value={filter} onChange={setFilter} />
          {!bot.status && !bot.error ? (
            <Loading />
          ) : shown.length === 0 ? (
            <Empty
              text={
                bot.events.length === 0
                  ? "Henüz olay yok."
                  : "Önemli bir olay yok. Tarama ve sinyal kayıtları için “Tümü”nü seçin."
              }
            />
          ) : (
            shown.map((event) => (
              <Card key={event.id}>
                <View style={{ flexDirection: "row", justifyContent: "space-between", gap: 8 }}>
                  <Label
                    style={{
                      fontWeight: "700",
                      color:
                        event.level === "error" ? colors.red : event.level === "warning" ? colors.gold : colors.text,
                    }}
                  >
                    {kindLabel(event.kind)}
                  </Label>
                  <Label muted style={{ fontSize: 12, flexShrink: 0 }}>
                    {timeText(event.at)}
                  </Label>
                </View>
                <Label muted>{event.message}</Label>
              </Card>
            ))
          )}
        </>
      ) : null}
    </BotPage>
  );
}
