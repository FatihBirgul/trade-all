import React from "react";
import { Pressable, View, useWindowDimensions } from "react-native";
import type { components } from "./api/schema";
import { useTheme } from "./theme";
import { Label } from "./ui";
import { MiniPriceChart } from "./MiniPriceChart";
import { money } from "./domain/safety";
export function MarketRow({
  quote,
  stale,
  onPress,
}: {
  quote: components["schemas"]["MarketQuote"];
  stale: boolean;
  onPress: () => void;
}) {
  const { colors } = useTheme(),
    { width, fontScale } = useWindowDimensions();
  const narrow = width / fontScale < 300;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={quote.symbol + " analiz et"}
      onPress={onPress}
      style={({ pressed }) => ({
        gap: 4,
        paddingVertical: 9,
        borderBottomWidth: 1,
        borderColor: colors.border,
        opacity: pressed ? 0.7 : 1,
      })}
    >
      <View
        style={{
          flexDirection: "row",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 4,
        }}
      >
        <Label style={{ fontWeight: "700" }}>{quote.symbol}</Label>
        <Label
          style={{
            color:
              Number(quote.change_percent_24h) < 0 ? colors.red : colors.green,
            fontWeight: "600",
          }}
        >
          {Number(quote.change_percent_24h).toLocaleString("tr-TR", {
            signDisplay: "always",
            maximumFractionDigits: 2,
          })}
          % · 24 sa.
        </Label>
      </View>
      <View
        style={{
          flexDirection: narrow ? "column" : "row",
          alignItems: narrow ? "stretch" : "center",
          gap: 8,
        }}
      >
        <View style={{ flex: narrow ? undefined : 3, minWidth: 0 }}>
          <Label
            style={{
              fontSize: 22,
              lineHeight: 28,
              fontWeight: "800",
              fontVariant: ["tabular-nums"],
            }}
          >
            {money(quote.price)} <Label muted>USDT</Label>
          </Label>
        </View>
        <View
          pointerEvents="none"
          style={{ flex: narrow ? undefined : 2, minWidth: 60 }}
        >
          {quote.chart_status === "available" ? (
            <MiniPriceChart prices={quote.history.map((p) => p.price)} />
          ) : (
            <Label muted>Grafik yok</Label>
          )}
        </View>
      </View>
      <Label muted style={{ fontSize: 11, lineHeight: 16 }}>
        {stale ? "Son başarılı veri" : "Son veri"} ·{" "}
        {new Date(quote.source_time_ms).toLocaleString("tr-TR")}
      </Label>
    </Pressable>
  );
}
