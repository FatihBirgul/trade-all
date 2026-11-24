import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React, { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Api } from "@/src/api/client";
import { Card, Disclaimer, SectionTitle } from "@/src/components/common";
import { colors, fonts, radius, spacing, type } from "@/src/theme";

function StatusRow({
  icon,
  label,
  value,
  ok,
  testID,
}: {
  icon: any;
  label: string;
  value: string;
  ok: boolean;
  testID?: string;
}) {
  return (
    <View style={styles.statusRow} testID={testID}>
      <Ionicons name={icon} size={18} color={colors.onSurfaceSecondary} />
      <View style={{ flex: 1 }}>
        <Text style={styles.statusLabel}>{label}</Text>
        <Text style={styles.statusValue}>{value}</Text>
      </View>
      <View style={[styles.dot, { backgroundColor: ok ? colors.success : colors.onSurfaceTertiary }]} />
    </View>
  );
}

export default function SettingsScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [cfg, setCfg] = useState<any>(null);

  useEffect(() => {
    Api.config().then(setCfg).catch(() => {});
  }, []);

  const p = cfg?.providers;

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <Pressable onPress={() => router.back()} hitSlop={10} testID="settings-back">
          <Ionicons name="chevron-back" size={24} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.title}>Settings</Text>
        <View style={{ width: 24 }} />
      </View>

      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing["3xl"] }}>
        <SectionTitle title="Data Providers" />
        <Card style={{ marginBottom: spacing.xl, gap: spacing.md }}>
          <StatusRow
            icon="pulse"
            label="Market Data"
            value={p ? `${p.market_data.name} · real-time` : "—"}
            ok={!!p?.market_data.available}
            testID="settings-market-status"
          />
          <View style={styles.sep} />
          <StatusRow
            icon="sparkles"
            label="AI Engine"
            value={p ? `${p.ai.name} · ${p.ai.model}` : "—"}
            ok={!!p?.ai.available}
            testID="settings-ai-status"
          />
          <View style={styles.sep} />
          <StatusRow
            icon="newspaper-outline"
            label="News"
            value={p?.news.available ? p.news.name : "Not configured"}
            ok={!!p?.news.available}
            testID="settings-news-status"
          />
        </Card>

        <SectionTitle title="Feature Status" />
        <Card style={{ marginBottom: spacing.xl }}>
          {[
            ["Live crypto prices (Binance)", "Fully working"],
            ["Technical analysis engine", "Fully working"],
            ["Candlestick & chart patterns", "Fully working"],
            ["AI chart-image vision analysis", "Fully working"],
            ["AI reasoning & scenarios", "Fully working"],
            ["Analysis history", "Fully working"],
            ["News feed", "Waiting for API key"],
            ["Outcome tracking / backtesting", "Architecture ready"],
          ].map(([f, s], i) => (
            <View key={i} style={[styles.featureRow, i > 0 && { borderTopWidth: 1, borderTopColor: colors.divider }]}>
              <Text style={styles.featureName}>{f}</Text>
              <Text
                style={[
                  styles.featureStatus,
                  { color: s === "Fully working" ? colors.success : colors.warning },
                ]}
              >
                {s}
              </Text>
            </View>
          ))}
        </Card>

        <SectionTitle title="About" />
        <Card style={{ marginBottom: spacing.xl }}>
          <Text style={styles.about}>
            Market AI is an analytical decision-support tool for crypto markets. It combines live market data,
            deterministic technical analysis and AI reasoning. It does not provide financial advice, execute trades, or
            guarantee outcomes. Always do your own research and manage risk.
          </Text>
        </Card>

        <Disclaimer />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  title: { color: colors.onSurface, fontFamily: fonts.displayBold, fontSize: type.xl, letterSpacing: 0.5 },
  statusRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  statusLabel: { color: colors.onSurface, fontFamily: fonts.bodySemi, fontSize: type.base },
  statusValue: { color: colors.onSurfaceTertiary, fontFamily: fonts.body, fontSize: type.sm, marginTop: 1 },
  dot: { width: 10, height: 10, borderRadius: 5 },
  sep: { height: 1, backgroundColor: colors.divider },
  featureRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingVertical: spacing.md },
  featureName: { color: colors.onSurfaceSecondary, fontFamily: fonts.body, fontSize: type.base, flex: 1 },
  featureStatus: { fontFamily: fonts.bodySemi, fontSize: type.sm },
  about: { color: colors.onSurfaceTertiary, fontFamily: fonts.body, fontSize: type.base, lineHeight: 21 },
});
