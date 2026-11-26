// Yön C — "Canlı": renkli üst alan, yuvarlak kartlar, iri başlıklar; bir bakışta durum.
import React from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { STAGES, STRATEGY, lots, minutesAgo, money, openPnl, positions, price, signed, signedR, stage, status, summary } from "./sample";

const c = { bg: "#F2F3FA", hero: "#2A2D7C", heroSoft: "#3D41A6", card: "#FFFFFF", text: "#16183A", muted: "#7A7F9D", line: "#E6E8F4", up: "#12A873", upSoft: "#DFF6EC", down: "#E5484D", downSoft: "#FDE8E8", sun: "#FFB020", sunSoft: "#FFF3D6" };
const tone = (v: number) => (v > 0 ? c.up : v < 0 ? c.down : c.text);
const soft = (v: number) => (v > 0 ? c.upSoft : v < 0 ? c.downSoft : c.line);
const card = { backgroundColor: c.card, borderRadius: 26, padding: 18, gap: 12, shadowColor: "#2A2D7C", shadowOpacity: 0.08, shadowRadius: 18, shadowOffset: { width: 0, height: 8 }, elevation: 3 } as const;

function Tabs({ active }: { active: string }) {
  const items = [["Panel", "grid"], ["Pozisyonlar", "swap-vertical"], ["Raporlar", "pie-chart"], ["Bildirimler", "notifications"], ["Ayarlar", "settings"]] as const;
  return (
    <View style={{ paddingHorizontal: 14, paddingBottom: 12, backgroundColor: c.bg }}>
      <View style={{ flexDirection: "row", backgroundColor: c.text, borderRadius: 28, padding: 8 }}>
        {items.map(([name, icon]) => (
          <View key={name} style={{ flex: name === active ? 2.2 : 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6, paddingVertical: 10, borderRadius: 22, backgroundColor: name === active ? "#FFFFFF" : "transparent" }}>
            <Ionicons name={icon} size={19} color={name === active ? c.hero : "#A9ADD0"} />
            {name === active ? <Text style={{ color: c.hero, fontWeight: "800", fontSize: 13 }}>{name}</Text> : null}
          </View>
        ))}
      </View>
    </View>
  );
}
const Pill = ({ label, color, bg }: { label: string; color: string; bg: string }) => (
  <View style={{ backgroundColor: bg, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 5 }}><Text style={{ color, fontSize: 12, fontWeight: "800" }}>{label}</Text></View>
);

export function Panel() {
  const periods = [["Bugün", summary.pnl.day], ["Bu hafta", summary.pnl.week], ["Bu ay", summary.pnl.month]] as const;
  return (
    <View style={{ flex: 1, backgroundColor: c.bg }}>
      <ScrollView contentContainerStyle={{ paddingBottom: 18 }}>
        <View style={{ backgroundColor: c.hero, borderBottomLeftRadius: 36, borderBottomRightRadius: 36, paddingHorizontal: 22, paddingTop: 26, paddingBottom: 54, gap: 6 }}>
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
            <Text style={{ color: "#FFFFFF", fontSize: 18, fontWeight: "800" }}>Trade Bot</Text>
            <Pill label={status.dry_run ? "DENEME MODU" : "● CANLI"} color="#FFFFFF" bg={c.heroSoft} />
          </View>
          <Text style={{ color: "#B9BCE8", fontSize: 14, marginTop: 18 }}>Toplam varlık</Text>
          <Text style={{ color: "#FFFFFF", fontSize: 42, fontWeight: "900", letterSpacing: -1 }}>{money(status.equity)}</Text>
          <Text style={{ color: "#B9BCE8", fontSize: 14 }}>Bakiye {money(status.balance)} · Serbest {money(status.margin_free)}</Text>
        </View>
        <View style={{ paddingHorizontal: 16, marginTop: -34, gap: 14 }}>
          <View style={{ flexDirection: "row", gap: 10 }}>
            {periods.map(([name, value]) => (
              <View key={name} style={{ ...card, flex: 1, padding: 14, gap: 8, borderRadius: 22 }}>
                <View style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: soft(value), alignItems: "center", justifyContent: "center" }}>
                  <Ionicons name={value >= 0 ? "trending-up" : "trending-down"} size={17} color={tone(value)} />
                </View>
                <Text style={{ color: c.muted, fontSize: 13 }}>{name}</Text>
                <Text style={{ color: tone(value), fontSize: 17, fontWeight: "900" }}>{signed(value, "")}</Text>
              </View>
            ))}
          </View>
          <View style={card}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
              <View style={{ width: 46, height: 46, borderRadius: 23, backgroundColor: status.stopped ? c.downSoft : c.upSoft, alignItems: "center", justifyContent: "center" }}>
                <Ionicons name={status.stopped ? "pause" : "pulse"} size={24} color={status.stopped ? c.down : c.up} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ color: c.text, fontSize: 19, fontWeight: "800" }}>{status.stopped ? "Bot durduruldu" : "Bot çalışıyor"}</Text>
                <Text style={{ color: c.muted, fontSize: 13 }}>Son tarama {minutesAgo(status.last_scan_at)} · Exness {status.stream_connected ? "bağlı" : "kopuk"}</Text>
              </View>
            </View>
            <View style={{ flexDirection: "row", gap: 8 }}>
              <Pill label={status.open_bot + " bot işlemi"} color={c.hero} bg="#E8E9FB" />
              <Pill label={status.open_manual + " elle işlem"} color={c.hero} bg="#E8E9FB" />
              <Pill label={signed(openPnl, "") + " açık"} color={tone(openPnl)} bg={soft(openPnl)} />
            </View>
            <Pressable style={{ backgroundColor: c.text, borderRadius: 18, paddingVertical: 16, alignItems: "center", flexDirection: "row", justifyContent: "center", gap: 8 }}>
              <Ionicons name="pause" size={18} color="#FFFFFF" /><Text style={{ color: "#FFFFFF", fontSize: 16, fontWeight: "800" }}>Botu durdur</Text>
            </Pressable>
            <Pressable style={{ alignItems: "center", paddingVertical: 4 }}><Text style={{ color: c.down, fontSize: 15, fontWeight: "700" }}>Tüm pozisyonları kapat</Text></Pressable>
          </View>
          <View style={{ ...card, backgroundColor: c.sunSoft, shadowOpacity: 0 }}>
            <Text style={{ color: c.text, fontSize: 16, fontWeight: "800" }}>Son 24 saatte</Text>
            <Text style={{ color: c.text, fontSize: 15, lineHeight: 22 }}>
              <Text style={{ fontWeight: "900" }}>{summary.activity.scans}</Text> tarama yapıldı, <Text style={{ fontWeight: "900" }}>{summary.activity.candidates}</Text> aday bulundu, <Text style={{ fontWeight: "900" }}>{summary.activity.opened}</Text> işlem açıldı. {summary.activity.news_blocked} aday haber nedeniyle beklendi.
            </Text>
          </View>
        </View>
      </ScrollView>
      <Tabs active="Panel" />
    </View>
  );
}

export function Positions() {
  return (
    <View style={{ flex: 1, backgroundColor: c.bg }}>
      <ScrollView contentContainerStyle={{ padding: 16, paddingTop: 24, gap: 14 }}>
        <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
          <View>
            <Text style={{ color: c.text, fontSize: 28, fontWeight: "900", letterSpacing: -0.5 }}>Pozisyonlar</Text>
            <Text style={{ color: c.muted, fontSize: 14 }}>{positions.length} açık · <Text style={{ color: tone(openPnl), fontWeight: "800" }}>{signed(openPnl)}</Text></Text>
          </View>
          <Pressable style={{ width: 50, height: 50, borderRadius: 25, backgroundColor: c.hero, alignItems: "center", justifyContent: "center" }}><Ionicons name="add" size={28} color="#FFFFFF" /></Pressable>
        </View>
        {positions.map((p) => (
          <View key={p.position_id} style={card}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
              <View style={{ width: 46, height: 46, borderRadius: 16, backgroundColor: p.side === "BUY" ? c.upSoft : c.downSoft, alignItems: "center", justifyContent: "center" }}>
                <Ionicons name={p.side === "BUY" ? "arrow-up" : "arrow-down"} size={24} color={p.side === "BUY" ? c.up : c.down} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ color: c.text, fontSize: 19, fontWeight: "900" }}>{p.symbol}</Text>
                <Text style={{ color: c.muted, fontSize: 13 }}>{p.side === "BUY" ? "Alış" : "Satış"} · {lots(p.volume)} · {p.origin === "bot" ? STRATEGY[p.strategy_id ?? ""] ?? "Bot" : "Elle"}</Text>
              </View>
              <View style={{ alignItems: "flex-end", gap: 4 }}>
                <Text style={{ color: tone(p.unrealized_pnl), fontSize: 20, fontWeight: "900" }}>{signed(p.unrealized_pnl, "")}</Text>
                <Pill label={signedR(p.r_multiple)} color={tone(p.r_multiple)} bg={soft(p.r_multiple)} />
              </View>
            </View>
            <View style={{ flexDirection: "row", backgroundColor: c.bg, borderRadius: 16, padding: 12 }}>
              {[["Giriş", price(p.entry, p.symbol)], ["Şimdi", price(p.price, p.symbol)], ["Stop", price(p.sl, p.symbol)], ["Hedef", price(p.tp2, p.symbol)]].map(([name, value]) => (
                <View key={name} style={{ flex: 1, gap: 2 }}><Text style={{ color: c.muted, fontSize: 12 }}>{name}</Text><Text style={{ color: c.text, fontSize: 14, fontWeight: "700" }}>{value}</Text></View>
              ))}
            </View>
            <View style={{ flexDirection: "row", alignItems: "center" }}>
              {STAGES.map((name, i) => (
                <React.Fragment key={name}>
                  {i > 0 ? <View style={{ flex: 1, height: 3, backgroundColor: i <= stage(p) ? c.hero : c.line }} /> : null}
                  <View style={{ alignItems: "center", gap: 4 }}>
                    <View style={{ width: 22, height: 22, borderRadius: 11, backgroundColor: i <= stage(p) ? c.hero : c.line, alignItems: "center", justifyContent: "center" }}>
                      {i <= stage(p) ? <Ionicons name="checkmark" size={14} color="#FFFFFF" /> : null}
                    </View>
                    <Text style={{ color: i <= stage(p) ? c.text : c.muted, fontSize: 11, fontWeight: i === stage(p) ? "800" : "500" }}>{name}</Text>
                  </View>
                </React.Fragment>
              ))}
            </View>
            <View style={{ flexDirection: "row", gap: 10 }}>
              <Pressable style={{ flex: 1, backgroundColor: "#E8E9FB", borderRadius: 16, paddingVertical: 13, alignItems: "center" }}><Text style={{ color: c.hero, fontWeight: "800" }}>Stop / hedef düzenle</Text></Pressable>
              <Pressable style={{ flex: 1, backgroundColor: c.downSoft, borderRadius: 16, paddingVertical: 13, alignItems: "center" }}><Text style={{ color: c.down, fontWeight: "800" }}>Kapat</Text></Pressable>
            </View>
          </View>
        ))}
      </ScrollView>
      <Tabs active="Pozisyonlar" />
    </View>
  );
}
