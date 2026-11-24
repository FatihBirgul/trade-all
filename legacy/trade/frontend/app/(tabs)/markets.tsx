import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useRef, useState } from "react";
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Api, Market } from "@/src/api/client";
import { useMarket } from "@/src/context/MarketContext";
import { changeColor, colors, fonts, logoUrl, radius, spacing, type } from "@/src/theme";
import { fmtPct, fmtPrice } from "@/src/utils/format";

export default function MarketsScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { setSelectedSymbol, isWatched, toggleWatch, watchlist } = useMarket();

  const [markets, setMarkets] = useState<Market[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const pollRef = useRef<any>(null);

  const load = useCallback(async () => {
    try {
      const d = await Api.markets();
      setMarkets(d.markets);
      setError(null);
    } catch (e: any) {
      setError(e.message || "Failed to sync live prices");
    } finally {
      setLoaded(true);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
      pollRef.current = setInterval(load, 12000);
      return () => clearInterval(pollRef.current);
    }, [load])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const filteredAll = markets.filter(
    (m) =>
      m.base.toLowerCase().includes(query.toLowerCase()) ||
      m.name.toLowerCase().includes(query.toLowerCase())
  );
  const watched = filteredAll.filter((m) => isWatched(m.symbol));
  const others = filteredAll.filter((m) => !isWatched(m.symbol));
  const listData: any[] = [
    ...(watched.length ? [{ __header: "Watchlist" }, ...watched] : []),
    ...(others.length ? [{ __header: watched.length ? "All Markets" : "" }, ...others] : []),
  ];

  const openAsset = (symbol: string) => {
    setSelectedSymbol(symbol);
    router.push("/(tabs)");
  };

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <Text style={styles.title}>Markets</Text>
        <Text style={styles.subtitle}>Live crypto · Binance</Text>
        <View style={styles.searchBox}>
          <Ionicons name="search" size={16} color={colors.onSurfaceTertiary} />
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder="Search asset"
            placeholderTextColor={colors.onSurfaceTertiary}
            style={styles.searchInput}
            testID="markets-search"
          />
        </View>
      </View>

      {error && (
        <View style={styles.banner} testID="markets-error-banner">
          <Ionicons name="warning" size={15} color={colors.error} />
          <Text style={styles.bannerText}>{error}</Text>
        </View>
      )}

      <FlatList
        data={listData}
        keyExtractor={(item) => (item.__header !== undefined ? `h-${item.__header || "all"}` : item.symbol)}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing["3xl"] }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.brand} />}
        renderItem={({ item }) => {
          if (item.__header !== undefined) {
            if (!item.__header) return <View style={{ height: spacing.sm }} />;
            return (
              <View style={styles.sectionHeader}>
                {item.__header === "Watchlist" && <Ionicons name="star" size={13} color={colors.brand} />}
                <Text style={styles.sectionHeaderText}>{item.__header}</Text>
              </View>
            );
          }
          const watchedNow = isWatched(item.symbol);
          return (
            <Pressable style={styles.row} onPress={() => openAsset(item.symbol)} testID={`market-row-${item.base}`}>
              <Pressable
                onPress={() => toggleWatch(item.symbol)}
                hitSlop={10}
                style={styles.star}
                testID={`market-watch-${item.base}`}
              >
                <Ionicons
                  name={watchedNow ? "star" : "star-outline"}
                  size={20}
                  color={watchedNow ? colors.brand : colors.onSurfaceTertiary}
                />
              </Pressable>
              <Image source={{ uri: logoUrl(item.base) }} style={styles.logo} contentFit="contain" transition={150} />
              <View style={{ flex: 1 }}>
                <Text style={styles.rowName}>{item.base}<Text style={styles.rowQuote}>/{item.quote}</Text></Text>
                <Text style={styles.rowFull}>{item.name}</Text>
              </View>
              {item.available ? (
                <View style={{ alignItems: "flex-end" }}>
                  <Text style={styles.rowPrice}>${fmtPrice(item.price)}</Text>
                  <Text style={[styles.rowChange, { color: changeColor(item.change_24h_pct) }]}>
                    {fmtPct(item.change_24h_pct)}
                  </Text>
                </View>
              ) : (
                <Text style={styles.unavailable}>N/A</Text>
              )}
            </Pressable>
          );
        }}
        ListEmptyComponent={
          loaded ? (
            <Text style={styles.empty}>No assets match your search.</Text>
          ) : null
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  header: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  title: { color: colors.onSurface, fontFamily: fonts.displayBold, fontSize: type["2xl"], letterSpacing: 0.5 },
  subtitle: { color: colors.onSurfaceTertiary, fontFamily: fonts.body, fontSize: type.sm, marginBottom: spacing.md },
  searchBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.surfaceTertiary,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    height: 42,
  },
  searchInput: { flex: 1, color: colors.onSurface, fontFamily: fonts.body, fontSize: type.base },
  banner: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.error + "1A",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  bannerText: { color: colors.error, fontFamily: fonts.body, fontSize: type.sm },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
  },
  logo: { width: 38, height: 38 },
  star: { paddingRight: 2 },
  sectionHeader: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: spacing.sm, marginBottom: spacing.xs },
  sectionHeaderText: { color: colors.onSurfaceTertiary, fontFamily: fonts.displaySemi, fontSize: type.sm, letterSpacing: 0.8, textTransform: "uppercase" },
  rowName: { color: colors.onSurface, fontFamily: fonts.displaySemi, fontSize: type.lg },
  rowQuote: { color: colors.onSurfaceTertiary, fontSize: type.base },
  rowFull: { color: colors.onSurfaceTertiary, fontFamily: fonts.body, fontSize: type.sm, marginTop: 1 },
  rowPrice: { color: colors.onSurface, fontFamily: fonts.displaySemi, fontSize: type.lg },
  rowChange: { fontFamily: fonts.bodyMedium, fontSize: type.sm, marginTop: 2 },
  unavailable: { color: colors.onSurfaceTertiary, fontFamily: fonts.bodyMedium, fontSize: type.base },
  empty: { color: colors.onSurfaceTertiary, fontFamily: fonts.body, fontSize: type.base, textAlign: "center", marginTop: spacing["2xl"] },
});
