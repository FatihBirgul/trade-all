import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Api } from "@/src/api/client";
import { AssetPickerModal } from "@/src/components/AssetPickerModal";
import { Card, DirectionBadge, Disclaimer, PrimaryButton, SectionTitle } from "@/src/components/common";
import { Sparkline } from "@/src/components/Sparkline";
import { useMarket } from "@/src/context/MarketContext";
import { changeColor, colors, fonts, logoUrl, radius, spacing, type } from "@/src/theme";
import { fmtPct, fmtPrice, timeAgo } from "@/src/utils/format";

export default function HomeScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { selectedSymbol, setSelectedSymbol, assets, defaultTimeframe, isWatched } = useMarket();

  const [detail, setDetail] = useState<any>(null);
  const [direction, setDirection] = useState<string>("neutral");
  const [error, setError] = useState<string | null>(null);
  const [recent, setRecent] = useState<any[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const pollRef = useRef<any>(null);

  const asset = assets.find((a) => a.symbol === selectedSymbol);
  const orderedAssets = [
    ...assets.filter((a) => isWatched(a.symbol)),
    ...assets.filter((a) => !isWatched(a.symbol)),
  ];

  const loadMarket = useCallback(async () => {
    try {
      const d = await Api.marketDetail(selectedSymbol, defaultTimeframe);
      setDetail(d);
      setError(null);
    } catch (e: any) {
      setError(e.message || "Market data unavailable");
    }
  }, [selectedSymbol, defaultTimeframe]);

  const loadTechnical = useCallback(async () => {
    try {
      const t: any = await Api.technical(selectedSymbol, defaultTimeframe);
      setDirection(t.direction);
    } catch {}
  }, [selectedSymbol, defaultTimeframe]);

  const loadRecent = useCallback(async () => {
    try {
      const r = await Api.history(5);
      setRecent(r.items || []);
    } catch {}
  }, []);

  useEffect(() => {
    setDetail(null);
    loadMarket();
    loadTechnical();
  }, [selectedSymbol, loadMarket, loadTechnical]);

  useFocusEffect(
    useCallback(() => {
      loadMarket();
      loadRecent();
      pollRef.current = setInterval(loadMarket, 15000);
      return () => clearInterval(pollRef.current);
    }, [loadMarket, loadRecent])
  );

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <View style={styles.brandRow}>
          <View style={styles.logoBadge}>
            <Ionicons name="pulse" size={18} color={colors.onBrand} />
          </View>
          <Text style={styles.brand}>MARKET<Text style={{ color: colors.brand }}>AI</Text></Text>
        </View>
        <Pressable onPress={() => router.push("/settings")} hitSlop={10} testID="home-settings-btn">
          <Ionicons name="settings-outline" size={22} color={colors.onSurfaceSecondary} />
        </Pressable>
      </View>

      <ScrollView
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing["3xl"] }}
        showsVerticalScrollIndicator={false}
      >
        {/* Asset selector row */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={{ gap: spacing.sm, paddingBottom: spacing.md }}
        >
          {orderedAssets.map((a) => {
            const active = a.symbol === selectedSymbol;
            const watched = isWatched(a.symbol);
            return (
              <Pressable
                key={a.symbol}
                onPress={() => setSelectedSymbol(a.symbol)}
                style={[styles.assetChip, active && styles.assetChipActive]}
                testID={`home-asset-chip-${a.base}`}
              >
                {watched && (
                  <Ionicons name="star" size={11} color={active ? colors.onBrand : colors.brand} />
                )}
                <Image source={{ uri: logoUrl(a.base) }} style={styles.chipLogo} contentFit="contain" />
                <Text style={[styles.assetChipText, active && { color: colors.onBrand }]}>{a.base}</Text>
              </Pressable>
            );
          })}
        </ScrollView>

        {/* Hero market card */}
        <Card style={{ marginBottom: spacing.lg }} testID="home-hero-card">
          <Pressable style={styles.heroTop} onPress={() => setPickerOpen(true)} testID="home-asset-select">
            <Image source={{ uri: logoUrl(asset?.base || "BTC") }} style={styles.heroLogo} contentFit="contain" />
            <View style={{ flex: 1 }}>
              <Text style={styles.heroName}>{asset?.base}/{asset?.quote}</Text>
              <Text style={styles.heroSub}>{asset?.name} · {defaultTimeframe}</Text>
            </View>
            <Ionicons name="chevron-down" size={18} color={colors.onSurfaceTertiary} />
          </Pressable>

          {error ? (
            <View style={styles.errorBox} testID="home-market-error">
              <Ionicons name="cloud-offline-outline" size={18} color={colors.error} />
              <Text style={styles.errorText}>Live market data unavailable</Text>
            </View>
          ) : (
            <>
              <View style={styles.priceRow}>
                <Text style={styles.price} testID="home-price">
                  {detail ? `$${fmtPrice(detail.price)}` : "$--"}
                </Text>
                <DirectionBadge direction={direction} testID="home-trend-badge" />
              </View>
              <View style={styles.metaRow}>
                <Text style={[styles.change, { color: changeColor(detail?.change_24h_pct) }]} testID="home-change">
                  {fmtPct(detail?.change_24h_pct)} <Text style={styles.changeLabel}>24h</Text>
                </Text>
                <Sparkline data={detail?.sparkline} width={130} height={44} testID="home-sparkline" />
              </View>
            </>
          )}
        </Card>

        <PrimaryButton
          label="NEW AI ANALYSIS"
          icon="scan"
          onPress={() => router.push("/(tabs)/analysis")}
          testID="home-new-analysis-btn"
          style={{ marginBottom: spacing.xl }}
        />

        <SectionTitle
          title="Recent Analyses"
          right={
            recent.length > 0 ? (
              <Pressable onPress={() => router.push("/(tabs)/history")} testID="home-see-all">
                <Text style={styles.seeAll}>See all</Text>
              </Pressable>
            ) : undefined
          }
        />
        {recent.length === 0 ? (
          <Card testID="home-recent-empty">
            <Text style={styles.emptyText}>No analyses yet. Upload your first chart to get started.</Text>
          </Card>
        ) : (
          recent.slice(0, 4).map((r) => (
            <Pressable key={r.id} onPress={() => router.push(`/result/${r.id}`)} testID={`recent-item-${r.id}`}>
              <Card style={styles.recentCard}>
                <Image source={{ uri: logoUrl(r.base) }} style={styles.recentLogo} contentFit="contain" />
                <View style={{ flex: 1 }}>
                  <Text style={styles.recentName}>{r.base}/{r.quote} · {r.timeframe}</Text>
                  <Text style={styles.recentSub}>{timeAgo(r.created_at)} · conf {Math.round(r.confidence)}%</Text>
                </View>
                <DirectionBadge direction={r.direction} />
              </Card>
            </Pressable>
          ))
        )}

        <View style={{ marginTop: spacing.xl }}>
          <Disclaimer testID="home-disclaimer" />
        </View>
      </ScrollView>

      <AssetPickerModal
        visible={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelect={setSelectedSymbol}
        selected={selectedSymbol}
      />
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
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  brandRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  logoBadge: { width: 30, height: 30, borderRadius: 8, backgroundColor: colors.brand, alignItems: "center", justifyContent: "center" },
  brand: { color: colors.onSurface, fontFamily: fonts.displayBold, fontSize: type.xl, letterSpacing: 1 },
  assetChip: {
    flexShrink: 0,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    height: 36,
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceTertiary,
    borderWidth: 1,
    borderColor: colors.border,
  },
  assetChipActive: { backgroundColor: colors.brand, borderColor: colors.brand },
  chipLogo: { width: 18, height: 18 },
  assetChipText: { color: colors.onSurfaceSecondary, fontFamily: fonts.bodySemi, fontSize: type.sm },
  heroTop: { flexDirection: "row", alignItems: "center", gap: spacing.md, marginBottom: spacing.lg },
  heroLogo: { width: 40, height: 40 },
  heroName: { color: colors.onSurface, fontFamily: fonts.displaySemi, fontSize: type.xl },
  heroSub: { color: colors.onSurfaceTertiary, fontFamily: fonts.body, fontSize: type.sm },
  priceRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  price: { color: colors.onSurface, fontFamily: fonts.displayBold, fontSize: type["4xl"], letterSpacing: 0.5 },
  metaRow: { flexDirection: "row", alignItems: "flex-end", justifyContent: "space-between", marginTop: spacing.xs },
  change: { fontFamily: fonts.displaySemi, fontSize: type.lg },
  changeLabel: { color: colors.onSurfaceTertiary, fontSize: type.sm, fontFamily: fonts.body },
  errorBox: { flexDirection: "row", alignItems: "center", gap: spacing.sm, paddingVertical: spacing.lg },
  errorText: { color: colors.error, fontFamily: fonts.bodyMedium, fontSize: type.base },
  seeAll: { color: colors.brand, fontFamily: fonts.bodySemi, fontSize: type.sm },
  emptyText: { color: colors.onSurfaceTertiary, fontFamily: fonts.body, fontSize: type.base, textAlign: "center" },
  recentCard: { flexDirection: "row", alignItems: "center", gap: spacing.md, marginBottom: spacing.sm, paddingVertical: spacing.md },
  recentLogo: { width: 32, height: 32 },
  recentName: { color: colors.onSurface, fontFamily: fonts.bodySemi, fontSize: type.base },
  recentSub: { color: colors.onSurfaceTertiary, fontFamily: fonts.body, fontSize: type.sm, marginTop: 2 },
});
