// Yön A — "Açık ve sakin": açık zemin, beyaz kartlar, tek vurgu rengi, büyük okunaklı rakamlar.
import React from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { STAGES, STRATEGY, lots, minutesAgo, money, openPnl, positions, price, signed, signedR, stage, status, summary } from "./sample";

const c = { bg: "#F4F6F9", card: "#FFFFFF", text: "#101828", muted: "#667085", line: "#E7EAF0", accent: "#2457F5", accentSoft: "#E9EEFF", up: "#0B9A6D", upSoft: "#E3F6EF", down: "#D43D51", downSoft: "#FCE9EC" };
const tone = (v: number) => (v > 0 ? c.up : v < 0 ? c.down : c.text);
const card = { backgroundColor: c.card, borderRadius: 20, padding: 18, gap: 12 } as const;

function Tabs({ active }: { active: string }) {
  const items = [["Panel", "speedometer-outline"], ["Pozisyonlar", "layers-outline"], ["Raporlar", "bar-chart-outline"], ["Bildirimler", "notifications-outline"], ["Ayarlar", "options-outline"]] as const;
  return (
    <View style={{ flexDirection: "row", backgroundColor: c.card, borderTopWidth: 1, borderTopColor: c.line, paddingVertical: 8 }}>
      {items.map(([name, icon]) => (
        <View key={name} style={{ flex: 1, alignItems: "center", gap: 2 }}>
          <Ionicons name={icon} size={22} color={name === active ? c.accent : c.muted} />
          <Text style={{ fontSize: 11, fontWeight: name === active ? "700" : "500", color: name === active ? c.accent : c.muted }}>{name}</Text>
        </View>
      ))}
    </View>
  );
}
function Frame({ title, active, right, children }: React.PropsWithChildren<{ title: string; active: string; right?: React.ReactNode }>) {
  return (
    <View style={{ flex: 1, backgroundColor: c.bg }}>
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 20, paddingTop: 22, paddingBottom: 10 }}>
        <Text style={{ fontSize: 26, fontWeight: "800", color: c.text, letterSpacing: -0.5 }}>{title}</Text>
        {right}
      </View>
      <ScrollView contentContainerStyle={{ padding: 16, paddingTop: 6, gap: 14 }}>{children}</ScrollView>
      <Tabs active={active} />
    </View>
  );
}
const Chip = ({ label, color, soft }: { label: string; color: string; soft: string }) => (
  <View style={{ backgroundColor: soft, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 }}>
    <Text style={{ color, fontSize: 12, fontWeight: "700" }}>{label}</Text>
  </View>
);
const Line = ({ name, value, color }: { name: string; value: string; color?: string }) => (
  <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
    <Text style={{ color: c.muted, fontSize: 15 }}>{name}</Text>
    <Text style={{ color: color ?? c.text, fontSize: 15, fontWeight: "600" }}>{value}</Text>
  </View>
);

export function Panel() {
  const periods = [["Bugün", summary.pnl.day], ["Bu hafta", summary.pnl.week], ["Bu ay", summary.pnl.month]] as const;
  const activity = [["Tarama", summary.activity.scans], ["Aday", summary.activity.candidates], ["Açılan", summary.activity.opened], ["Gölge", summary.activity.shadowed]] as const;
  return (
    <Frame title="Panel" active="Panel" right={<Chip label={status.dry_run ? "DENEME" : "CANLI"} color={status.dry_run ? c.accent : c.up} soft={status.dry_run ? c.accentSoft : c.upSoft} />}>
      <View style={card}>
        <Text style={{ color: c.muted, fontSize: 14 }}>Varlık</Text>
        <Text style={{ color: c.text, fontSize: 38, fontWeight: "800", letterSpacing: -1 }}>{money(status.equity)}</Text>
        <View style={{ height: 1, backgroundColor: c.line }} />
        <Line name="Bakiye" value={money(status.balance)} />
        <Line name="Serbest teminat" value={money(status.margin_free)} />
      </View>
      <View style={{ flexDirection: "row", gap: 10 }}>
        {periods.map(([name, value]) => (
          <View key={name} style={{ ...card, flex: 1, padding: 14, gap: 6 }}>
            <Text style={{ color: c.muted, fontSize: 13 }}>{name}</Text>
            <Text style={{ color: tone(value), fontSize: 17, fontWeight: "800" }}>{signed(value, "")}</Text>
          </View>
        ))}
      </View>
      <View style={card}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: status.stopped ? c.down : c.up }} />
          <Text style={{ color: c.text, fontSize: 18, fontWeight: "700", flex: 1 }}>{status.stopped ? "Bot durduruldu" : "Bot çalışıyor"}</Text>
        </View>
        <Line name="Son tarama" value={minutesAgo(status.last_scan_at)} />
        <Line name="Exness bağlantısı" value={status.stream_connected ? "Bağlı" : "Kopuk"} color={status.stream_connected ? c.up : c.down} />
        <Line name="Açık işlemler" value={status.open_bot + " bot · " + status.open_manual + " elle"} />
        <View style={{ flexDirection: "row", gap: 10, marginTop: 4 }}>
          <Pressable style={{ flex: 1, backgroundColor: c.text, borderRadius: 14, paddingVertical: 14, alignItems: "center" }}>
            <Text style={{ color: "#FFF", fontSize: 16, fontWeight: "700" }}>Durdur</Text>
          </Pressable>
          <Pressable style={{ flex: 1, borderWidth: 1.5, borderColor: c.down, borderRadius: 14, paddingVertical: 14, alignItems: "center" }}>
            <Text style={{ color: c.down, fontSize: 16, fontWeight: "700" }}>Hepsini kapat</Text>
          </Pressable>
        </View>
      </View>
      <View style={card}>
        <Text style={{ color: c.text, fontSize: 16, fontWeight: "700" }}>Son 24 saatte bot</Text>
        <View style={{ flexDirection: "row" }}>
          {activity.map(([name, value]) => (
            <View key={name} style={{ flex: 1, gap: 2 }}>
              <Text style={{ color: c.text, fontSize: 22, fontWeight: "800" }}>{value}</Text>
              <Text style={{ color: c.muted, fontSize: 13 }}>{name}</Text>
            </View>
          ))}
        </View>
      </View>
    </Frame>
  );
}

export function Positions() {
  return (
    <Frame title="Pozisyonlar" active="Pozisyonlar" right={<Pressable style={{ backgroundColor: c.accent, borderRadius: 999, paddingHorizontal: 14, paddingVertical: 9, flexDirection: "row", gap: 4, alignItems: "center" }}><Ionicons name="add" size={18} color="#FFF" /><Text style={{ color: "#FFF", fontWeight: "700" }}>Elle işlem</Text></Pressable>}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", paddingHorizontal: 4 }}>
        <Text style={{ color: c.muted, fontSize: 15 }}>{positions.length} açık pozisyon</Text>
        <Text style={{ color: tone(openPnl), fontSize: 15, fontWeight: "700" }}>{signed(openPnl)}</Text>
      </View>
      {positions.map((p) => (
        <View key={p.position_id} style={card}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <View style={{ flex: 1, gap: 3 }}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
                <Text style={{ color: c.text, fontSize: 20, fontWeight: "800" }}>{p.symbol}</Text>
                <Chip label={p.side === "BUY" ? "AL" : "SAT"} color={p.side === "BUY" ? c.up : c.down} soft={p.side === "BUY" ? c.upSoft : c.downSoft} />
              </View>
              <Text style={{ color: c.muted, fontSize: 13 }}>{lots(p.volume)} · {p.origin === "bot" ? STRATEGY[p.strategy_id ?? ""] ?? "Bot" : "Elle"}</Text>
            </View>
            <View style={{ alignItems: "flex-end" }}>
              <Text style={{ color: tone(p.unrealized_pnl), fontSize: 19, fontWeight: "800" }}>{signed(p.unrealized_pnl, "")}</Text>
              <Text style={{ color: tone(p.r_multiple), fontSize: 12, fontWeight: "600" }}>{signedR(p.r_multiple)}</Text>
            </View>
          </View>
          <View style={{ flexDirection: "row", gap: 10 }}>
            {[["Giriş", price(p.entry, p.symbol)], ["Şimdi", price(p.price, p.symbol)], ["Zarar durdur", price(p.sl, p.symbol)], ["Kâr al", price(p.tp2, p.symbol)]].map(([name, value]) => (
              <View key={name} style={{ flex: 1, gap: 2 }}>
                <Text style={{ color: c.muted, fontSize: 12 }}>{name}</Text>
                <Text style={{ color: c.text, fontSize: 14, fontWeight: "600" }}>{value}</Text>
              </View>
            ))}
          </View>
          <View style={{ gap: 6 }}>
            <View style={{ flexDirection: "row", gap: 4 }}>
              {STAGES.map((name, i) => (<View key={name} style={{ flex: 1, height: 5, borderRadius: 3, backgroundColor: i <= stage(p) ? c.accent : c.line }} />))}
            </View>
            <Text style={{ color: c.muted, fontSize: 12 }}>Kademeli stop: <Text style={{ color: c.text, fontWeight: "700" }}>{STAGES[stage(p)]}</Text></Text>
          </View>
          <View style={{ flexDirection: "row", gap: 10 }}>
            <Pressable style={{ flex: 1, backgroundColor: c.accentSoft, borderRadius: 12, paddingVertical: 12, alignItems: "center" }}><Text style={{ color: c.accent, fontWeight: "700" }}>SL / TP düzenle</Text></Pressable>
            <Pressable style={{ flex: 1, borderWidth: 1.5, borderColor: c.line, borderRadius: 12, paddingVertical: 12, alignItems: "center" }}><Text style={{ color: c.text, fontWeight: "700" }}>Kapat</Text></Pressable>
          </View>
        </View>
      ))}
    </Frame>
  );
}
