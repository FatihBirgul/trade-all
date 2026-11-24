import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Api } from "@/src/api/client";
import { Card, DirectionBadge, Loading, OutcomeBadge, PrimaryButton, StateView } from "@/src/components/common";
import { colors, fonts, logoUrl, radius, spacing, type } from "@/src/theme";
import { fmtPrice, timeAgo } from "@/src/utils/format";

export default function HistoryScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [perf, setPerf] = useState<any>(null);
  const [evaluating, setEvaluating] = useState(false);

  const load = useCallback(async () => {
    try {
      const [d, p] = await Promise.all([Api.history(50), Api.performance()]);
      setItems(d.items || []);
      setPerf(p);
    } catch {
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const refreshOutcomes = async () => {
    setEvaluating(true);
    try {
      const res = await Api.evaluateAll();
      setPerf(res.performance);
      const d = await Api.history(50);
      setItems(d.items || []);
    } catch {
    } finally {
      setEvaluating(false);
    }
  };

  const remove = async (id: string) => {
    setItems((prev) => prev.filter((i) => i.id !== id));
    try {
      await Api.deleteHistory(id);
    } catch {}
  };

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <Text style={styles.title}>History</Text>
        <Text style={styles.subtitle}>Saved analyses · real-outcome hit-rate</Text>
      </View>

      {loading ? (
        <Loading text="Loading history…" />
      ) : (
        <FlatList
          data={items}
          keyExtractor={(i) => i.id}
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing["3xl"] }}
          ListHeaderComponent={
            items.length > 0 ? (
              <Card style={{ marginBottom: spacing.lg }} testID="history-performance-card">
                <View style={styles.perfTop}>
                  <Text style={styles.perfTitle}>Performance</Text>
                  <Pressable
                    onPress={refreshOutcomes}
                    disabled={evaluating}
                    style={styles.refreshBtn}
                    testID="history-refresh-outcomes"
                  >
                    <Ionicons
                      name={evaluating ? "sync" : "refresh"}
                      size={14}
                      color={colors.brand}
                    />
                    <Text style={styles.refreshText}>{evaluating ? "Checking…" : "Refresh outcomes"}</Text>
                  </Pressable>
                </View>
                <View style={styles.perfRow}>
                  <View style={styles.perfStat}>
                    <Text style={[styles.perfBig, { color: colors.brand }]} testID="history-hit-rate">
                      {perf?.hit_rate != null ? `${perf.hit_rate}%` : "--"}
                    </Text>
                    <Text style={styles.perfLabel}>Hit-rate</Text>
                  </View>
                  <View style={styles.perfStat}>
                    <Text style={[styles.perfBig, { color: colors.success }]}>{perf?.wins ?? 0}</Text>
                    <Text style={styles.perfLabel}>Wins</Text>
                  </View>
                  <View style={styles.perfStat}>
                    <Text style={[styles.perfBig, { color: colors.error }]}>{perf?.losses ?? 0}</Text>
                    <Text style={styles.perfLabel}>Losses</Text>
                  </View>
                  <View style={styles.perfStat}>
                    <Text style={[styles.perfBig, { color: colors.onSurfaceTertiary }]}>{perf?.pending ?? 0}</Text>
                    <Text style={styles.perfLabel}>Pending</Text>
                  </View>
                </View>
                <Text style={styles.perfNote}>
                  Target 1 hit before invalidation, checked against real prices. Small samples aren't statistically
                  meaningful — not a guarantee of future results.
                </Text>
              </Card>
            ) : null
          }
          renderItem={({ item }) => (
            <Pressable onPress={() => router.push(`/result/${item.id}`)} testID={`history-item-${item.id}`}>
              <View style={styles.card}>
                {item.has_image && item.image_base64 ? (
                  <Image
                    source={{ uri: `data:image/jpeg;base64,${item.image_base64}` }}
                    style={styles.thumb}
                    contentFit="cover"
                  />
                ) : (
                  <View style={[styles.thumb, styles.thumbFallback]}>
                    <Image source={{ uri: logoUrl(item.base) }} style={{ width: 34, height: 34 }} contentFit="contain" />
                  </View>
                )}
                <View style={{ flex: 1 }}>
                  <View style={styles.cardTop}>
                    <Text style={styles.cardName}>
                      {item.base}/{item.quote} · {item.timeframe}
                    </Text>
                    <DirectionBadge direction={item.direction} />
                  </View>
                  <Text style={styles.cardPrice}>${fmtPrice(item.price_at_analysis)}</Text>
                  <View style={styles.cardBottom}>
                    <View style={styles.cardBottomLeft}>
                      <OutcomeBadge status={item.outcome?.status} testID={`history-outcome-${item.id}`} />
                      <Text style={styles.cardDate}>{timeAgo(item.created_at)} · {Math.round(item.confidence)}%</Text>
                    </View>
                    <Pressable onPress={() => remove(item.id)} hitSlop={10} testID={`history-delete-${item.id}`}>
                      <Ionicons name="trash-outline" size={18} color={colors.onSurfaceTertiary} />
                    </Pressable>
                  </View>
                </View>
              </View>
            </Pressable>
          )}
          ListEmptyComponent={
            <StateView
              icon="time-outline"
              title="No past analyses yet"
              subtitle="Run an AI analysis and it will be saved here automatically."
              testID="history-empty"
            />
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  header: { paddingHorizontal: spacing.lg, paddingBottom: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.border },
  title: { color: colors.onSurface, fontFamily: fonts.displayBold, fontSize: type["2xl"], letterSpacing: 0.5 },
  subtitle: { color: colors.onSurfaceTertiary, fontFamily: fonts.body, fontSize: type.sm },
  card: {
    flexDirection: "row",
    gap: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  thumb: { width: 76, height: 76, borderRadius: radius.sm, backgroundColor: colors.surfaceTertiary },
  thumbFallback: { alignItems: "center", justifyContent: "center" },
  cardTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  cardName: { color: colors.onSurface, fontFamily: fonts.displaySemi, fontSize: type.lg, flex: 1 },
  cardPrice: { color: colors.onSurfaceSecondary, fontFamily: fonts.body, fontSize: type.base, marginTop: 2 },
  cardBottom: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: spacing.sm },
  cardBottomLeft: { flexDirection: "row", alignItems: "center", gap: spacing.sm, flex: 1 },
  cardDate: { color: colors.onSurfaceTertiary, fontFamily: fonts.body, fontSize: type.sm },
  perfTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.md },
  perfTitle: { color: colors.onSurface, fontFamily: fonts.displaySemi, fontSize: type.lg, letterSpacing: 0.5, textTransform: "uppercase" },
  refreshBtn: { flexDirection: "row", alignItems: "center", gap: 5 },
  refreshText: { color: colors.brand, fontFamily: fonts.bodySemi, fontSize: type.sm },
  perfRow: { flexDirection: "row", justifyContent: "space-between" },
  perfStat: { alignItems: "center", flex: 1 },
  perfBig: { fontFamily: fonts.displayBold, fontSize: type["2xl"] },
  perfLabel: { color: colors.onSurfaceTertiary, fontFamily: fonts.body, fontSize: type.sm, marginTop: 2 },
  perfNote: { color: colors.onSurfaceTertiary, fontFamily: fonts.body, fontSize: type.sm, lineHeight: 16, marginTop: spacing.md },
});
