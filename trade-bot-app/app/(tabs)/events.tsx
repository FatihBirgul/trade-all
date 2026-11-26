import React, { useState } from "react";
import { View } from "react-native";
import { isImportant, kindLabel } from "../../src/bot/notifications";
import { timeText } from "../../src/bot/presentation";
import { useBot } from "../../src/bot/state";
import type { BotEvent } from "../../src/bot/types";
import { DataGate } from "../../src/ui/DataGate";
import { Button, Card, Empty, IconBubble, Screen, Segmented, T } from "../../src/ui/kit";
import { c } from "../../src/ui/theme";

const FILTERS = [["important", "Önemli"], ["all", "Tümü"]] as const;
type IconName = React.ComponentProps<typeof IconBubble>["icon"];
const ICONS: Record<string, IconName> = {
  trade_opened: "arrow-up-circle", trade_closed: "checkmark-done", sl_breakeven: "shield-checkmark", scan: "search",
  signal: "flash", signal_observed: "eye", bot_started: "play", bot_halted: "hand-left", connection_lost: "cloud-offline",
  settings_changed: "options", device_paired: "phone-portrait", order_rejected: "close-circle",
};

function look(event: BotEvent): { icon: IconName; color: string; bg: string } {
  if (event.level === "error") return { icon: ICONS[event.kind] ?? "alert-circle", color: c.down, bg: c.downSoft };
  if (event.level === "warning") return { icon: ICONS[event.kind] ?? "warning", color: c.sun, bg: c.sunSoft };
  return { icon: ICONS[event.kind] ?? "ellipse", color: c.hero, bg: c.tint };
}

export default function Events() {
  const bot = useBot();
  const [filter, setFilter] = useState<(typeof FILTERS)[number][0]>("important");
  const events = filter === "all" ? bot.events : bot.events.filter(isImportant);
  return (
    <Screen testID="screen-events" title="Bildirimler" subtitle={bot.events.length ? "Son " + bot.events.length + " kayıt" : undefined}>
      <DataGate>
        <Segmented options={FILTERS} value={filter} onChange={setFilter} />
        {events.length === 0 ? (
          filter === "important" && bot.events.length > 0 ? (
            <Empty icon="notifications-off" title="Önemli bir olay yok" text="Tarama ve sinyal kayıtları “Tümü” görünümünde.">
              <Button testID="show-all" title={"Tümünü göster (" + bot.events.length + ")"} kind="tonal" onPress={() => setFilter("all")} />
            </Empty>
          ) : (
            <Empty icon="notifications-off" title="Henüz kayıt yok" text="Bot bir şey yaptığında (tarama, işlem, uyarı) burada görünür." />
          )
        ) : (
          <Card testID="event-list" style={{ gap: 16 }}>
            {events.slice(0, 120).map((event) => {
              const style = look(event);
              return (
                <View key={event.id} testID={"event-" + event.id} style={{ flexDirection: "row", gap: 12 }}>
                  <IconBubble icon={style.icon} color={style.color} bg={style.bg} size={38} />
                  <View style={{ flex: 1, gap: 2 }}>
                    <View style={{ flexDirection: "row", justifyContent: "space-between", gap: 8 }}>
                      <T weight="800" size={14} style={{ flexShrink: 1 }}>{kindLabel(event.kind)}</T>
                      <T muted size={12}>{timeText(event.at)}</T>
                    </View>
                    <T size={14}>{event.message}</T>
                  </View>
                </View>
              );
            })}
          </Card>
        )}
      </DataGate>
    </Screen>
  );
}
