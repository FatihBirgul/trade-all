// Yön B — "Terminal": koyu, yoğun, tablo düzeni; rakamlar eş aralıklı yazıyla hizalı.
import React from "react";
import { Platform, Pressable, ScrollView, Text, View } from "react-native";
import { STAGES, STRATEGY, lots, minutesAgo, money, openPnl, positions, price, signed, signedR, stage, status, summary } from "./sample";

const c = { bg: "#0A0E13", panel: "#0F151C", line: "#1C2733", text: "#DCE5EE", muted: "#6C8096", up: "#2ED89A", down: "#FF5D6E", warn: "#F2B84B" };
const mono = Platform.select({ web: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace", default: "monospace" }) as string;
const tone = (v: number) => (v > 0 ? c.up : v < 0 ? c.down : c.text);
const num = { fontFamily: mono, color: c.text, fontSize: 14 } as const;
const label = { color: c.muted, fontSize: 11, letterSpacing: 1.2, fontWeight: "700" } as const;

function Tabs({ active }: { active: string }) {
  return (
    <View style={{ flexDirection: "row", borderTopWidth: 1, borderTopColor: c.line, backgroundColor: c.panel }}>
      {["PANEL", "POZİSYON", "RAPOR", "OLAYLAR", "AYAR"].map((name) => (
        <View key={name} style={{ flex: 1, alignItems: "center", paddingVertical: 14, borderTopWidth: 2, borderTopColor: name === active ? c.up : "transparent" }}>
          <Text style={{ fontSize: 11, letterSpacing: 1, fontWeight: "700", color: name === active ? c.text : c.muted }}>{name}</Text>
        </View>
      ))}
    </View>
  );
}
function Frame({ active, children }: React.PropsWithChildren<{ active: string }>) {
  return (
    <View style={{ flex: 1, backgroundColor: c.bg }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 14, paddingHorizontal: 16, paddingTop: 18, paddingBottom: 12, borderBottomWidth: 1, borderBottomColor: c.line }}>
        <Text style={{ color: status.dry_run ? c.warn : c.up, fontSize: 12, fontWeight: "800", letterSpacing: 1 }}>● {status.dry_run ? "DENEME" : "CANLI"}</Text>
        <Text style={{ ...label, color: status.stream_connected ? c.text : c.down }}>EXNESS {status.stream_connected ? "BAĞLI" : "KOPUK"}</Text>
        <Text style={{ ...label, flex: 1, textAlign: "right" }}>TARAMA {minutesAgo(status.last_scan_at).toUpperCase()}</Text>
      </View>
      <ScrollView>{children}</ScrollView>
      <Tabs active={active} />
    </View>
  );
}
const Section = ({ title, right, children }: React.PropsWithChildren<{ title: string; right?: string }>) => (
  <View style={{ borderBottomWidth: 1, borderBottomColor: c.line, paddingHorizontal: 16, paddingVertical: 14, gap: 10 }}>
    <View style={{ flexDirection: "row", justifyContent: "space-between" }}><Text style={label}>{title}</Text>{right ? <Text style={label}>{right}</Text> : null}</View>
    {children}
  </View>
);
const Row = ({ name, value, color }: { name: string; value: string; color?: string }) => (
  <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
    <Text style={{ color: c.muted, fontSize: 14 }}>{name}</Text>
    <Text style={{ ...num, color: color ?? c.text }}>{value}</Text>
  </View>
);
const Key = ({ title, color }: { title: string; color: string }) => (
  <Pressable style={{ flex: 1, borderWidth: 1, borderColor: color, paddingVertical: 12, alignItems: "center" }}>
    <Text style={{ color, fontSize: 13, fontWeight: "800", letterSpacing: 1 }}>{title}</Text>
  </Pressable>
);

export function Panel() {
  const scale = Math.max(Math.abs(summary.pnl.day), Math.abs(summary.pnl.week), Math.abs(summary.pnl.month));
  return (
    <Frame active="PANEL">
      <Section title="VARLIK" right={status.currency}>
        <Text style={{ fontFamily: mono, color: c.text, fontSize: 40, fontWeight: "700", letterSpacing: -1 }}>{money(status.equity, "").trim()}</Text>
        <Row name="Bakiye" value={money(status.balance, "").trim()} />
        <Row name="Serbest teminat" value={money(status.margin_free, "").trim()} />
        <Row name="Açık kâr/zarar" value={signed(openPnl, "").trim()} color={tone(openPnl)} />
      </Section>
      <Section title="KÂR / ZARAR" right="KAPANAN + AÇIK">
        {([["Bugün", summary.pnl.day, summary.trades.day], ["Hafta", summary.pnl.week, summary.trades.week], ["Ay", summary.pnl.month, summary.trades.month]] as const).map(([name, value, count]) => (
          <View key={name} style={{ gap: 5 }}>
            <View style={{ flexDirection: "row", alignItems: "baseline" }}>
              <Text style={{ color: c.text, fontSize: 14, width: 64 }}>{name}</Text>
              <Text style={{ color: c.muted, fontSize: 12, flex: 1 }}>{count} işlem</Text>
              <Text style={{ ...num, fontSize: 16, color: tone(value) }}>{signed(value, "").trim()}</Text>
            </View>
            <View style={{ height: 3, backgroundColor: c.line }}><View style={{ height: 3, width: `${(Math.abs(value) / scale) * 100}%`, backgroundColor: tone(value) }} /></View>
          </View>
        ))}
      </Section>
      <Section title="BOT" right={status.stopped ? "DURDURULDU" : "ÇALIŞIYOR"}>
        <Row name="Açık işlem" value={status.open_bot + " bot / " + status.open_manual + " elle"} />
        <Row name="24s tarama / aday / açılan" value={summary.activity.scans + " / " + summary.activity.candidates + " / " + summary.activity.opened} />
        <Row name="Gölge işlem · haber engeli" value={summary.activity.shadowed + " · " + summary.activity.news_blocked} />
        <View style={{ flexDirection: "row", gap: 10, marginTop: 4 }}><Key title="DURDUR" color={c.warn} /><Key title="HEPSİNİ KAPAT" color={c.down} /></View>
      </Section>
    </Frame>
  );
}

export function Positions() {
  return (
    <Frame active="POZİSYON">
      <Section title={positions.length + " AÇIK POZİSYON"} right={signed(openPnl)}>
        <Key title="+ ELLE İŞLEM AÇ" color={c.text} />
      </Section>
      {positions.map((p) => (
        <View key={p.position_id} style={{ borderBottomWidth: 1, borderBottomColor: c.line, paddingHorizontal: 16, paddingVertical: 14, gap: 9, borderLeftWidth: 3, borderLeftColor: p.side === "BUY" ? c.up : c.down }}>
          <View style={{ flexDirection: "row", alignItems: "baseline", gap: 10 }}>
            <Text style={{ color: c.text, fontSize: 18, fontWeight: "800", letterSpacing: 0.5 }}>{p.symbol}</Text>
            <Text style={{ color: p.side === "BUY" ? c.up : c.down, fontSize: 13, fontWeight: "800" }}>{p.side === "BUY" ? "AL" : "SAT"}</Text>
            <Text style={{ ...num, color: c.muted, fontSize: 13, flex: 1 }}>{lots(p.volume)}</Text>
            <Text style={{ ...num, fontSize: 18, fontWeight: "700", color: tone(p.unrealized_pnl) }}>{signed(p.unrealized_pnl, "").trim()}</Text>
          </View>
          <View style={{ flexDirection: "row" }}>
            {[["GİRİŞ", price(p.entry, p.symbol)], ["ŞİMDİ", price(p.price, p.symbol)], ["SL", price(p.sl, p.symbol)], ["TP", price(p.tp2, p.symbol)]].map(([name, value]) => (
              <View key={name} style={{ flex: 1, gap: 3 }}><Text style={{ ...label, fontSize: 10 }}>{name}</Text><Text style={{ ...num, fontSize: 13 }}>{value}</Text></View>
            ))}
          </View>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <Text style={{ fontFamily: mono, color: c.up, fontSize: 13 }}>{"■".repeat(stage(p) + 1)}<Text style={{ color: c.line }}>{"■".repeat(2 - stage(p))}</Text></Text>
            <Text style={{ ...label, flex: 1 }}>{STAGES[stage(p)].toUpperCase()} · {p.origin === "bot" ? (STRATEGY[p.strategy_id ?? ""] ?? "BOT").toUpperCase() : "ELLE"}</Text>
            <Text style={{ ...num, fontSize: 13, color: tone(p.r_multiple) }}>{signedR(p.r_multiple)}</Text>
          </View>
          <View style={{ flexDirection: "row", gap: 10 }}><Key title="SL / TP" color={c.muted} /><Key title="KAPAT" color={c.down} /></View>
        </View>
      ))}
    </Frame>
  );
}
