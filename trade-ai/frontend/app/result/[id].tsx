import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useEffect, useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Api } from "@/src/api/client";
import {
  Card,
  DirectionBadge,
  Loading,
  PatternChip,
  ScoreBar,
  SectionTitle,
  Segmented,
  StateView,
} from "@/src/components/common";
import {
  colors,
  directionColor,
  fonts,
  logoUrl,
  radius,
  spacing,
  type,
} from "@/src/theme";
import { fmtPrice } from "@/src/utils/format";

function LevelRow({
  label,
  value,
  color,
  testID,
}: {
  label: string;
  value?: number | null;
  color?: string;
  testID?: string;
}) {
  return (
    <View style={styles.levelRow} testID={testID}>
      <Text style={styles.levelLabel}>{label}</Text>
      <Text style={[styles.levelValue, color ? { color } : null]}>
        {value != null ? `$${fmtPrice(value)}` : "--"}
      </Text>
    </View>
  );
}

function IndicatorCell({
  label,
  value,
}: {
  label: string;
  value: any;
}) {
  return (
    <View style={styles.indCell}>
      <Text style={styles.indLabel}>{label}</Text>
      <Text style={styles.indValue}>{value ?? "--"}</Text>
    </View>
  );
}

export default function ResultScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const insets = useSafeAreaInsets();
  const router = useRouter();

  const [data, setData] = useState<any>(null);
  const [error, setError] = useState(false);
  const [scenario, setScenario] = useState("bullish");

  useEffect(() => {
    Api.historyDetail(String(id))
      .then((d) => {
        setData(d);
        setScenario(d.direction || "neutral");
      })
      .catch(() => setError(true));
  }, [id]);

  if (error) {
    return (
      <View style={styles.container}>
        <StateView
          icon="alert-circle-outline"
          title="Analysis not found"
          subtitle="It may have been deleted."
        />
      </View>
    );
  }

  if (!data) {
    return (
      <View style={styles.container}>
        <Loading text="Loading analysis..." />
      </View>
    );
  }

  const direction = data.direction || "neutral";
  const isWait = direction === "neutral";

  const dirColor = directionColor(direction);

  const bullishBias =
    direction === "bullish"
      ? 50 + data.confidence / 2
      : direction === "bearish"
        ? 50 - data.confidence / 2
        : 50;

  const ind = data.indicators || {};
  const zones = data.zones || {};
  const vision = data.vision || {};
  const scores = data.scores || {};

  const hasVision =
    vision &&
    Object.keys(vision).length > 0 &&
    vision.available !== false;

  const rr = zones.risk_reward;

  const waitReason =
    rr != null && rr < 1
      ? `Risk / Reward is too low (${rr}:1). The setup is not attractive enough to trade.`
      : "No valid directional trade setup was confirmed on this timeframe.";

  return (
    <View style={styles.container}>
      {/* Hero */}
      <View>
        {data.has_image && data.image_base64 ? (
          <View style={styles.hero}>
            <Image
              source={{
                uri: `data:image/jpeg;base64,${data.image_base64}`,
              }}
              style={styles.heroImg}
              contentFit="cover"
            />
            <LinearGradient
              colors={["#000000CC", "transparent", "#090B0FEE"]}
              locations={[0, 0.4, 1]}
              style={StyleSheet.absoluteFill}
            />
          </View>
        ) : (
          <LinearGradient
            colors={[colors.surfaceTertiary, colors.surface]}
            style={styles.heroPlain}
          >
            <Image
              source={{ uri: logoUrl(data.base) }}
              style={{ width: 56, height: 56 }}
              contentFit="contain"
            />
          </LinearGradient>
        )}

        <View
          style={[
            styles.heroHeader,
            { paddingTop: insets.top + spacing.xs },
          ]}
        >
          <View style={styles.backBtn}>
            <Ionicons
              name="chevron-back"
              size={24}
              color="#fff"
              onPress={() => {
                if (router.canGoBack()) {
                  router.back();
                } else {
                  router.replace("/");
                }
              }}
              testID="result-back"
            />
          </View>
        </View>
      </View>

      <ScrollView
        contentContainerStyle={{
          padding: spacing.lg,
          paddingBottom: 90,
        }}
        showsVerticalScrollIndicator={false}
      >
        {/* Title */}
        <View style={styles.titleRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.asset}>
              {data.base}/{data.quote}
            </Text>

            <Text style={styles.tf}>
              {data.timeframe} · ${fmtPrice(data.price_at_analysis)}
            </Text>
          </View>

          <DirectionBadge
            direction={direction}
            testID="result-direction"
          />
        </View>

        {/* WAIT / NO TRADE */}
        {isWait && (
          <Card style={styles.waitCard} testID="result-wait">
            <View style={styles.waitIconWrap}>
              <Ionicons
                name="pause-circle"
                size={34}
                color={colors.warning}
              />
            </View>

            <View style={{ flex: 1 }}>
              <Text style={styles.waitTitle}>WAIT / İŞLEM YOK</Text>

              <Text style={styles.waitSubtitle}>
                Bu analiz şu anda işlem açmak için yeterli kalitede bir setup
                üretmedi.
              </Text>

              <Text style={styles.waitReason}>{waitReason}</Text>
            </View>
          </Card>
        )}

        {/* Confidence */}
        <Card style={{ marginBottom: spacing.lg }} testID="result-gauge">
          <View style={styles.gaugeTop}>
            <Text style={styles.gaugeLabel}>Signal Strength</Text>

            <Text
              style={[
                styles.gaugeValue,
                { color: isWait ? colors.warning : dirColor },
              ]}
            >
              {Math.round(data.confidence)}%
            </Text>
          </View>

          <View style={styles.gaugeTrack}>
            <View
              style={[
                styles.gaugeFill,
                {
                  width: `${bullishBias}%`,
                  backgroundColor: colors.success,
                },
              ]}
            />

            <View
              style={[
                styles.gaugeFillRight,
                {
                  width: `${100 - bullishBias}%`,
                  backgroundColor: colors.error,
                },
              ]}
            />

            <View
              style={[
                styles.gaugeMarker,
                {
                  left: `${bullishBias}%`,
                },
              ]}
            />
          </View>

          <View style={styles.gaugeLegend}>
            <Text
              style={[
                styles.legendText,
                { color: colors.error },
              ]}
            >
              Bearish
            </Text>

            <Text
              style={[
                styles.legendText,
                { color: colors.success },
              ]}
            >
              Bullish
            </Text>
          </View>

          <Text style={styles.gaugeNote}>
            Analytical signal strength, not a statistical probability of
            winning.
          </Text>
        </Card>

        {/* Summary */}
        {data.summary ? (
          <Card
            style={{ marginBottom: spacing.lg }}
            testID="result-summary"
          >
            <Text style={styles.summary}>{data.summary}</Text>
          </Card>
        ) : null}

        {/* Component scores */}
        <SectionTitle title="Component Scores" />

        <Card style={{ marginBottom: spacing.lg }}>
          <ScoreBar label="Trend" value={scores.trend ?? 0} />
          <ScoreBar label="Momentum" value={scores.momentum ?? 0} />
          <ScoreBar label="Volume" value={scores.volume ?? 0} />
          <ScoreBar label="Pattern" value={scores.pattern ?? 0} />
          <ScoreBar label="Structure" value={scores.structure ?? 0} />
          <ScoreBar label="News" value={scores.news ?? 0} />
        </Card>

        {/* Trade setup */}
        <SectionTitle title="Trade Setup" />

        {isWait ? (
          <Card style={{ marginBottom: spacing.lg }}>
            <Text style={styles.waitSetupTitle}>
              No executable setup
            </Text>

            <Text style={styles.waitSetupText}>
              Entry, target and invalidation levels are intentionally not
              provided because the current setup does not meet the minimum
              trade-quality rules.
            </Text>

            {rr != null && (
              <View style={styles.rrRow}>
                <Text style={styles.levelLabel}>
                  Calculated Risk / Reward
                </Text>

                <Text
                  style={[
                    styles.levelValue,
                    {
                      color:
                        rr < 1
                          ? colors.error
                          : colors.onSurface,
                    },
                  ]}
                >
                  {rr}:1
                </Text>
              </View>
            )}
          </Card>
        ) : (
          <>
            <Segmented
              options={["bullish", "bearish", "neutral"]}
              value={scenario}
              onChange={setScenario}
              testIDPrefix="result-scenario"
            />

            <Card
              style={{
                marginTop: spacing.md,
                marginBottom: spacing.lg,
              }}
            >
              <Text style={styles.scenarioText}>
                {data.scenarios?.[scenario] || "No scenario detail."}
              </Text>

              <View style={styles.levelsBox}>
                <LevelRow
                  label="Entry zone"
                  value={zones.entry_low}
                  testID="result-entry"
                />

                <LevelRow
                  label="Entry (upper)"
                  value={zones.entry_high}
                />

                <LevelRow
                  label="Target 1"
                  value={zones.target_1}
                  color={colors.success}
                  testID="result-t1"
                />

                <LevelRow
                  label="Target 2"
                  value={zones.target_2}
                  color={colors.success}
                />

                <LevelRow
                  label="Invalidation"
                  value={zones.invalidation}
                  color={colors.error}
                  testID="result-invalidation"
                />

                <View style={styles.levelRow}>
                  <Text style={styles.levelLabel}>
                    Risk / Reward
                  </Text>

                  <Text style={styles.levelValue}>
                    {rr != null ? `${rr}:1` : "--"}
                  </Text>
                </View>
              </View>

              <View style={styles.legendChips}>
                <View style={styles.legendChip}>
                  <View
                    style={[
                      styles.legendDot,
                      { backgroundColor: colors.success },
                    ]}
                  />
                  <Text style={styles.legendChipText}>Target</Text>
                </View>

                <View style={styles.legendChip}>
                  <View
                    style={[
                      styles.legendDot,
                      { backgroundColor: colors.error },
                    ]}
                  />
                  <Text style={styles.legendChipText}>
                    Invalidation
                  </Text>
                </View>

                <View style={styles.legendChip}>
                  <View
                    style={[
                      styles.legendDot,
                      { backgroundColor: colors.brand },
                    ]}
                  />
                  <Text style={styles.legendChipText}>Entry</Text>
                </View>
              </View>
            </Card>
          </>
        )}

        {/* Detected patterns */}
        <SectionTitle title="Detected Patterns" />

        <View style={styles.chipWrap}>
          {[
            ...(data.chart_patterns || []),
            ...(data.candlestick_patterns || []),
          ].length === 0 ? (
            <Text style={styles.noneText}>
              No significant patterns detected on this timeframe.
            </Text>
          ) : (
            <>
              {(data.chart_patterns || []).map(
                (p: any, i: number) => (
                  <PatternChip
                    key={`c${i}`}
                    label={p.name}
                    tone={p.classification}
                    testID={`chart-pattern-${i}`}
                  />
                )
              )}

              {(data.candlestick_patterns || []).map(
                (p: any, i: number) => (
                  <PatternChip
                    key={`k${i}`}
                    label={p.name}
                    tone={p.classification}
                    testID={`candle-pattern-${i}`}
                  />
                )
              )}
            </>
          )}
        </View>

        {/* Pattern explanations */}
        {(data.chart_patterns || [])
          .slice(0, 3)
          .map((p: any, i: number) => (
            <Card key={`ce${i}`} style={styles.explainCard}>
              <View style={styles.explainTop}>
                <Text style={styles.explainName}>{p.name}</Text>

                <Text
                  style={[
                    styles.explainTag,
                    {
                      color: directionColor(
                        p.classification
                      ),
                    },
                  ]}
                >
                  {p.classification} · {p.confidence}%
                </Text>
              </View>

              <Text style={styles.explainText}>
                {p.explanation}
              </Text>
            </Card>
          ))}

        {/* Technical indicators */}
        <SectionTitle title="Technical Indicators" />

        <Card style={{ marginBottom: spacing.lg }}>
          <View style={styles.indGrid}>
            <IndicatorCell
              label="RSI (14)"
              value={ind.rsi14}
            />

            <IndicatorCell
              label="MACD Hist"
              value={ind.macd_hist}
            />

            <IndicatorCell
              label="Stoch RSI %K"
              value={ind.stoch_rsi_k}
            />

            <IndicatorCell
              label="EMA 50"
              value={
                ind.ema50
                  ? `$${fmtPrice(ind.ema50)}`
                  : "--"
              }
            />

            <IndicatorCell
              label="EMA 200"
              value={
                ind.ema200
                  ? `$${fmtPrice(ind.ema200)}`
                  : "--"
              }
            />

            <IndicatorCell
              label="ATR %"
              value={
                ind.atr_pct
                  ? `${ind.atr_pct}%`
                  : "--"
              }
            />

            <IndicatorCell
              label="Vol vs MA"
              value={
                ind.volume_ratio
                  ? `${ind.volume_ratio}x`
                  : "--"
              }
            />

            <IndicatorCell
              label="BB Mid"
              value={
                ind.bb_middle
                  ? `$${fmtPrice(ind.bb_middle)}`
                  : "--"
              }
            />
          </View>
        </Card>

        {/* News sentiment */}
        <SectionTitle title="News Sentiment" />

        <Card
          style={{
            marginBottom: spacing.lg,
            flexDirection: "row",
            alignItems: "center",
            gap: spacing.sm,
          }}
        >
          <Ionicons
            name="newspaper-outline"
            size={18}
            color={colors.onSurfaceTertiary}
          />

          <Text style={styles.newsNote}>
            {data.news_sentiment?.note ||
              "News data unavailable — this analysis is technical-only."}
          </Text>
        </Card>

        {/* Vision analysis */}
        {hasVision && (
          <>
            <SectionTitle title="Chart Image Analysis" />

            <Card
              style={{ marginBottom: spacing.lg }}
              testID="result-vision"
            >
              {vision.detected_symbol && (
                <Text style={styles.visionRow}>
                  Detected:{" "}
                  <Text style={styles.visionStrong}>
                    {vision.detected_symbol}
                  </Text>{" "}
                  {vision.detected_timeframe
                    ? `· ${vision.detected_timeframe}`
                    : ""}{" "}
                  ({vision.symbol_confidence})
                </Text>
              )}

              {vision.trend && (
                <Text style={styles.visionRow}>
                  Visible trend:{" "}
                  <Text style={styles.visionStrong}>
                    {vision.trend}
                  </Text>
                </Text>
              )}

              {(vision.chart_patterns || []).length > 0 && (
                <Text style={styles.visionRow}>
                  Patterns:{" "}
                  {(vision.chart_patterns || []).join(", ")}
                </Text>
              )}

              {(vision.support_resistance || []).length > 0 && (
                <Text style={styles.visionRow}>
                  S/R:{" "}
                  {(vision.support_resistance || []).join(", ")}
                </Text>
              )}

              {vision.notes && (
                <Text style={styles.visionNotes}>
                  {vision.notes}
                </Text>
              )}
            </Card>
          </>
        )}

        {/* Reasons */}
        <SectionTitle title="Supporting Evidence" />

        <Card style={{ marginBottom: spacing.lg }}>
          {(data.supporting_reasons || []).length === 0 ? (
            <Text style={styles.noneText}>
              No strong supporting evidence.
            </Text>
          ) : (
            (data.supporting_reasons || []).map(
              (r: string, i: number) => (
                <View
                  key={i}
                  style={styles.reasonRow}
                  testID={`support-reason-${i}`}
                >
                  <Ionicons
                    name="checkmark-circle"
                    size={16}
                    color={colors.success}
                    style={{ marginTop: 2 }}
                  />

                  <Text style={styles.reasonText}>{r}</Text>
                </View>
              )
            )
          )}
        </Card>

        <SectionTitle title="Contradicting / Risks" />

        <Card>
          {(data.contradicting_reasons || []).length === 0 ? (
            <Text style={styles.noneText}>
              No major contradicting signals.
            </Text>
          ) : (
            (data.contradicting_reasons || []).map(
              (r: string, i: number) => (
                <View
                  key={i}
                  style={styles.reasonRow}
                  testID={`contra-reason-${i}`}
                >
                  <Ionicons
                    name="alert-circle"
                    size={16}
                    color={colors.warning}
                    style={{ marginTop: 2 }}
                  />

                  <Text style={styles.reasonText}>{r}</Text>
                </View>
              )
            )
          )}
        </Card>
      </ScrollView>

      {/* Sticky disclaimer */}
      <View
        style={[
          styles.footer,
          { paddingBottom: insets.bottom + spacing.sm },
        ]}
      >
        <Ionicons
          name="warning"
          size={14}
          color={colors.warning}
        />

        <Text style={styles.footerText}>
          Not financial advice · no outcome is guaranteed · manage your own
          risk
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.surface,
  },

  hero: {
    height: 240,
    backgroundColor: colors.surfaceTertiary,
  },

  heroImg: {
    width: "100%",
    height: "100%",
  },

  heroPlain: {
    height: 160,
    alignItems: "center",
    justifyContent: "center",
  },

  heroHeader: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    paddingHorizontal: spacing.lg,
  },

  backBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#00000066",
    alignItems: "center",
    justifyContent: "center",
  },

  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.lg,
  },

  asset: {
    color: colors.onSurface,
    fontFamily: fonts.displayBold,
    fontSize: type["3xl"],
  },

  tf: {
    color: colors.onSurfaceTertiary,
    fontFamily: fonts.body,
    fontSize: type.base,
    marginTop: 2,
  },

  waitCard: {
    marginBottom: spacing.lg,
    flexDirection: "row",
    gap: spacing.md,
    borderWidth: 1,
    borderColor: colors.warning,
  },

  waitIconWrap: {
    width: 40,
    alignItems: "center",
    justifyContent: "flex-start",
    paddingTop: 2,
  },

  waitTitle: {
    color: colors.warning,
    fontFamily: fonts.displayBold,
    fontSize: type.xl,
    marginBottom: spacing.xs,
  },

  waitSubtitle: {
    color: colors.onSurfaceSecondary,
    fontFamily: fonts.body,
    fontSize: type.base,
    lineHeight: 20,
  },

  waitReason: {
    color: colors.onSurfaceTertiary,
    fontFamily: fonts.bodyMedium,
    fontSize: type.sm,
    lineHeight: 18,
    marginTop: spacing.sm,
  },

  waitSetupTitle: {
    color: colors.warning,
    fontFamily: fonts.displaySemi,
    fontSize: type.lg,
    marginBottom: spacing.sm,
  },

  waitSetupText: {
    color: colors.onSurfaceTertiary,
    fontFamily: fonts.body,
    fontSize: type.base,
    lineHeight: 20,
  },

  rrRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: spacing.lg,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },

  gaugeTop: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.md,
  },

  gaugeLabel: {
    color: colors.onSurfaceSecondary,
    fontFamily: fonts.bodyMedium,
    fontSize: type.base,
  },

  gaugeValue: {
    fontFamily: fonts.displayBold,
    fontSize: type["2xl"],
  },

  gaugeTrack: {
    height: 12,
    borderRadius: 6,
    backgroundColor: colors.surfaceTertiary,
    flexDirection: "row",
    overflow: "hidden",
  },

  gaugeFill: {
    height: 12,
  },

  gaugeFillRight: {
    height: 12,
  },

  gaugeMarker: {
    position: "absolute",
    top: -3,
    width: 3,
    height: 18,
    backgroundColor: colors.onSurface,
    marginLeft: -1.5,
  },

  gaugeLegend: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: spacing.sm,
  },

  legendText: {
    fontFamily: fonts.bodyMedium,
    fontSize: type.sm,
  },

  gaugeNote: {
    color: colors.onSurfaceTertiary,
    fontFamily: fonts.body,
    fontSize: type.sm,
    marginTop: spacing.md,
    lineHeight: 17,
  },

  summary: {
    color: colors.onSurfaceSecondary,
    fontFamily: fonts.body,
    fontSize: type.base,
    lineHeight: 21,
  },

  scenarioText: {
    color: colors.onSurfaceSecondary,
    fontFamily: fonts.body,
    fontSize: type.base,
    lineHeight: 21,
    marginBottom: spacing.md,
  },

  levelsBox: {
    borderTopWidth: 1,
    borderTopColor: colors.divider,
    paddingTop: spacing.sm,
  },

  levelRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 7,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
  },

  levelLabel: {
    color: colors.onSurfaceTertiary,
    fontFamily: fonts.body,
    fontSize: type.base,
  },

  levelValue: {
    color: colors.onSurface,
    fontFamily: fonts.displaySemi,
    fontSize: type.base,
  },

  legendChips: {
    flexDirection: "row",
    gap: spacing.lg,
    marginTop: spacing.md,
  },

  legendChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
  },

  legendDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },

  legendChipText: {
    color: colors.onSurfaceTertiary,
    fontFamily: fonts.body,
    fontSize: type.sm,
  },

  chipWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginBottom: spacing.md,
  },

  noneText: {
    color: colors.onSurfaceTertiary,
    fontFamily: fonts.body,
    fontSize: type.base,
  },

  explainCard: {
    marginBottom: spacing.sm,
  },

  explainTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: spacing.xs,
  },

  explainName: {
    color: colors.onSurface,
    fontFamily: fonts.displaySemi,
    fontSize: type.base,
  },

  explainTag: {
    fontFamily: fonts.bodySemi,
    fontSize: type.sm,
    textTransform: "capitalize",
  },

  explainText: {
    color: colors.onSurfaceTertiary,
    fontFamily: fonts.body,
    fontSize: type.sm,
    lineHeight: 18,
  },

  indGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
  },

  indCell: {
    width: "50%",
    paddingVertical: spacing.sm,
  },

  indLabel: {
    color: colors.onSurfaceTertiary,
    fontFamily: fonts.body,
    fontSize: type.sm,
  },

  indValue: {
    color: colors.onSurface,
    fontFamily: fonts.displaySemi,
    fontSize: type.lg,
    marginTop: 2,
  },

  newsNote: {
    flex: 1,
    color: colors.onSurfaceTertiary,
    fontFamily: fonts.body,
    fontSize: type.sm,
    lineHeight: 18,
  },

  visionRow: {
    color: colors.onSurfaceSecondary,
    fontFamily: fonts.body,
    fontSize: type.base,
    marginBottom: spacing.xs,
  },

  visionStrong: {
    fontFamily: fonts.bodySemi,
    color: colors.onSurface,
  },

  visionNotes: {
    color: colors.onSurfaceTertiary,
    fontFamily: fonts.body,
    fontSize: type.sm,
    marginTop: spacing.sm,
    lineHeight: 18,
  },

  reasonRow: {
    flexDirection: "row",
    gap: spacing.sm,
    paddingVertical: 5,
  },

  reasonText: {
    flex: 1,
    color: colors.onSurfaceSecondary,
    fontFamily: fonts.body,
    fontSize: type.base,
    lineHeight: 20,
  },

  footer: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    backgroundColor: colors.brandTertiary,
    paddingTop: spacing.sm,
    paddingHorizontal: spacing.lg,
  },

  footerText: {
    color: colors.brandSecondary,
    fontFamily: fonts.bodyMedium,
    fontSize: type.sm,
  },
});