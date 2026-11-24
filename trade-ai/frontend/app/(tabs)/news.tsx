import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect } from "expo-router";
import React, { useCallback, useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Api } from "@/src/api/client";
import { Card, DirectionBadge, Loading, StateView } from "@/src/components/common";
import { useMarket } from "@/src/context/MarketContext";
import { colors, fonts, spacing, type } from "@/src/theme";
import { timeAgo } from "@/src/utils/format";

export default function NewsScreen() {
  const insets = useSafeAreaInsets();
  const { selectedSymbol, assets } = useMarket();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const asset = assets.find((a) => a.symbol === selectedSymbol);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await Api.news(asset?.base);
      setData(d);
    } catch {
      setData({ available: false, message: "Could not fetch news." });
    } finally {
      setLoading(false);
    }
  }, [asset?.base]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <Text style={styles.title}>News</Text>
        <Text style={styles.subtitle}>Sentiment-tagged headlines</Text>
      </View>

      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing["3xl"] }}>
        {loading ? (
          <Loading text="Loading news…" />
        ) : data?.available ? (
          (data.articles || []).map((a: any, i: number) => (
            <Card key={i} style={styles.newsCard}>
              <View style={{ flex: 1 }}>
                <Text style={styles.newsTitle}>{a.headline}</Text>
                <Text style={styles.newsMeta}>
                  {a.source} · {timeAgo(a.published_at)}
                </Text>
              </View>
              <DirectionBadge direction={a.sentiment?.label} />
            </Card>
          ))
        ) : (
          <StateView
            icon="newspaper-outline"
            title="News feed unavailable"
            subtitle={
              data?.message ||
              "A news provider has not been configured yet. Technical analysis continues to work without news."
            }
            testID="news-unavailable"
          />
        )}

        <Card style={{ marginTop: spacing.lg, flexDirection: "row", gap: spacing.sm }}>
          <Ionicons name="construct-outline" size={18} color={colors.onSurfaceTertiary} />
          <Text style={styles.note}>
            The news architecture is ready. When a news API key is added, headlines will appear here with source,
            timestamp, sentiment, relevance and an AI summary — labelled honestly, never fabricated.
          </Text>
        </Card>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  header: { paddingHorizontal: spacing.lg, paddingBottom: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.border },
  title: { color: colors.onSurface, fontFamily: fonts.displayBold, fontSize: type["2xl"], letterSpacing: 0.5 },
  subtitle: { color: colors.onSurfaceTertiary, fontFamily: fonts.body, fontSize: type.sm },
  newsCard: { flexDirection: "row", alignItems: "center", gap: spacing.md, marginBottom: spacing.sm },
  newsTitle: { color: colors.onSurface, fontFamily: fonts.bodySemi, fontSize: type.base, lineHeight: 20 },
  newsMeta: { color: colors.onSurfaceTertiary, fontFamily: fonts.body, fontSize: type.sm, marginTop: 4 },
  note: { flex: 1, color: colors.onSurfaceTertiary, fontFamily: fonts.body, fontSize: type.sm, lineHeight: 18 },
});
