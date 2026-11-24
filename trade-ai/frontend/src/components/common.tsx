import { Ionicons } from "@expo/vector-icons";
import React from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
  ViewStyle,
} from "react-native";

import {
  colors,
  directionColor,
  fonts,
  radius,
  spacing,
  type,
} from "@/src/theme";

// ---------------- Card ----------------
export function Card({
  children,
  style,
  testID,
}: {
  children: React.ReactNode;
  style?: ViewStyle;
  testID?: string;
}) {
  return (
    <View
      style={[styles.card, style]}
      testID={testID}
    >
      {children}
    </View>
  );
}

// ---------------- Section heading ----------------
export function SectionTitle({
  title,
  right,
  testID,
}: {
  title: string;
  right?: React.ReactNode;
  testID?: string;
}) {
  return (
    <View
      style={styles.sectionRow}
      testID={testID}
    >
      <Text style={styles.sectionTitle}>
        {title}
      </Text>

      {right}
    </View>
  );
}

// ---------------- Outcome badge ----------------
export function OutcomeBadge({
  status,
  testID,
}: {
  status?: string;
  testID?: string;
}) {
  const map: Record<
    string,
    {
      c: string;
      label: string;
      icon: string;
    }
  > = {
    win: {
      c: colors.success,
      label: "WIN",
      icon: "checkmark-done",
    },

    loss: {
      c: colors.error,
      label: "LOSS",
      icon: "close",
    },

    pending: {
      c: colors.onSurfaceTertiary,
      label: "PENDING",
      icon: "hourglass-outline",
    },

    ambiguous: {
      c: colors.onSurfaceTertiary,
      label: "AMBIGUOUS",
      icon: "help-circle-outline",
    },

    neutral: {
      c: colors.onSurfaceTertiary,
      label: "N/A",
      icon: "remove",
    },

    unresolvable: {
      c: colors.onSurfaceTertiary,
      label: "N/A",
      icon: "remove",
    },
  };

  const m =
    map[status || "pending"] ||
    map.pending;

  return (
    <View
      style={[
        styles.outcome,
        {
          borderColor: m.c + "55",
          backgroundColor: m.c + "1A",
        },
      ]}
      testID={testID}
    >
      <Ionicons
        name={m.icon as any}
        size={11}
        color={m.c}
      />

      <Text
        style={[
          styles.outcomeText,
          { color: m.c },
        ]}
      >
        {m.label}
      </Text>
    </View>
  );
}

// ---------------- Directional badge ----------------
export function DirectionBadge({
  direction,
  testID,
}: {
  direction?: string;
  testID?: string;
}) {
  const c = directionColor(direction);

  const label = (
    direction || "neutral"
  ).toUpperCase();

  const icon =
    direction === "bullish"
      ? "trending-up"
      : direction === "bearish"
      ? "trending-down"
      : "remove";

  return (
    <View
      style={[
        styles.badge,
        {
          backgroundColor: c + "22",
          borderColor: c + "55",
        },
      ]}
      testID={testID}
    >
      <Ionicons
        name={icon as any}
        size={13}
        color={c}
      />

      <Text
        style={[
          styles.badgeText,
          { color: c },
        ]}
      >
        {label}
      </Text>
    </View>
  );
}

// ---------------- Pattern chip ----------------
export function PatternChip({
  label,
  tone,
  testID,
}: {
  label: string;
  tone?: string;
  testID?: string;
}) {
  const c = directionColor(tone);

  return (
    <View
      style={[
        styles.chip,
        {
          borderColor: c + "55",
        },
      ]}
      testID={testID}
    >
      <View
        style={[
          styles.chipDot,
          {
            backgroundColor: c,
          },
        ]}
      />

      <Text style={styles.chipText}>
        {label}
      </Text>
    </View>
  );
}

// ---------------- Segmented control ----------------
export function Segmented({
  options,
  value,
  onChange,
  testIDPrefix,
}: {
  options: string[];
  value: string;
  onChange: (v: string) => void;
  testIDPrefix?: string;
}) {
  return (
    <View style={styles.segment}>
      {options.map((opt) => {
        const active =
          opt === value;

        return (
          <Pressable
            key={opt}
            onPress={() => onChange(opt)}
            style={[
              styles.segmentItem,
              active &&
                styles.segmentItemActive,
            ]}
            testID={
              testIDPrefix
                ? `${testIDPrefix}-${opt}`
                : undefined
            }
          >
            <Text
              style={[
                styles.segmentText,
                active &&
                  styles.segmentTextActive,
              ]}
            >
              {opt}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

// ---------------- Primary button ----------------
export function PrimaryButton({
  label,
  onPress,
  loading,
  disabled,
  icon,
  testID,
  style,
}: {
  label: string;
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
  icon?: any;
  testID?: string;
  style?: ViewStyle;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      style={[
        styles.primaryBtn,
        (disabled || loading) && {
          opacity: 0.5,
        },
        style,
      ]}
      testID={testID}
    >
      {loading ? (
        <ActivityIndicator
          color={colors.onBrand}
        />
      ) : (
        <>
          {icon && (
            <Ionicons
              name={icon}
              size={18}
              color={colors.onBrand}
            />
          )}

          <Text
            style={styles.primaryBtnText}
          >
            {label}
          </Text>
        </>
      )}
    </Pressable>
  );
}

// ---------------- Score bar ----------------
export function ScoreBar({
  label,
  value,
  testID,
}: {
  label: string;
  value: number;
  testID?: string;
}) {
  const pct = Math.min(
    100,
    Math.abs(value)
  );

  const bullish = value >= 0;

  const c =
    value > 8
      ? colors.success
      : value < -8
      ? colors.error
      : colors.onSurfaceTertiary;

  return (
    <View
      style={styles.scoreRow}
      testID={testID}
    >
      <Text
        style={styles.scoreLabel}
      >
        {label}
      </Text>

      <View
        style={styles.scoreTrack}
      >
        <View
          style={styles.scoreCenter}
        />

        <View
          style={[
            styles.scoreFill,
            {
              backgroundColor: c,
              width: `${pct / 2}%`,
              left: bullish
                ? "50%"
                : undefined,
              right: bullish
                ? undefined
                : "50%",
            },
          ]}
        />
      </View>

      <Text
        style={[
          styles.scoreVal,
          { color: c },
        ]}
      >
        {value > 0 ? "+" : ""}
        {Math.round(value)}
      </Text>
    </View>
  );
}

// ---------------- Empty / error / loading states ----------------
export function StateView({
  icon,
  title,
  subtitle,
  action,
  testID,
}: {
  icon: any;
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  testID?: string;
}) {
  return (
    <View
      style={styles.state}
      testID={testID}
    >
      <View
        style={styles.stateIcon}
      >
        <Ionicons
          name={icon}
          size={30}
          color={
            colors.onSurfaceTertiary
          }
        />
      </View>

      <Text
        style={styles.stateTitle}
      >
        {title}
      </Text>

      {subtitle ? (
        <Text
          style={styles.stateSub}
        >
          {subtitle}
        </Text>
      ) : null}

      {action ? (
        <View
          style={{
            marginTop: spacing.lg,
          }}
        >
          {action}
        </View>
      ) : null}
    </View>
  );
}

export function Loading({
  text,
}: {
  text?: string;
}) {
  return (
    <View
      style={styles.loading}
      testID="loading-view"
    >
      <ActivityIndicator
        color={colors.brand}
      />

      {text ? (
        <Text
          style={styles.loadingText}
        >
          {text}
        </Text>
      ) : null}
    </View>
  );
}

// ---------------- Disclaimer ----------------
export function Disclaimer({
  compact,
  testID,
}: {
  compact?: boolean;
  testID?: string;
}) {
  return (
    <View
      style={[
        styles.disclaimer,
        compact && {
          padding: spacing.sm,
        },
      ]}
      testID={testID}
    >
      <Ionicons
        name="warning-outline"
        size={14}
        color={colors.warning}
      />

      <Text
        style={styles.disclaimerText}
      >
        Not financial advice. Market AI is an analytical decision-support tool — no result is guaranteed.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor:
      colors.surfaceSecondary,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
  },

  sectionRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent:
      "space-between",
    marginBottom: spacing.md,
  },

  sectionTitle: {
    color: colors.onSurface,
    fontFamily:
      fonts.displaySemi,
    fontSize: type.lg,
    letterSpacing: 0.5,
    textTransform:
      "uppercase",
  },

  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal:
      spacing.sm,
    paddingVertical: 4,
    borderRadius:
      radius.sm,
    borderWidth: 1,
  },

  badgeText: {
    fontFamily:
      fonts.bodySemi,
    fontSize: type.sm,
    letterSpacing: 0.5,
  },

  outcome: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: radius.sm,
    borderWidth: 1,
  },

  outcomeText: {
    fontFamily:
      fonts.bodySemi,
    fontSize: 10,
    letterSpacing: 0.5,
  },

  chip: {
    flexShrink: 0,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal:
      spacing.md,
    height: 32,
    borderRadius:
      radius.pill,
    borderWidth: 1,
    backgroundColor:
      colors.surfaceTertiary,
  },

  chipDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },

  chipText: {
    color:
      colors.onSurfaceSecondary,
    fontFamily:
      fonts.bodyMedium,
    fontSize: type.sm,
  },

  segment: {
    flexDirection: "row",
    backgroundColor:
      colors.surfaceTertiary,
    borderRadius: radius.md,
    padding: 3,
  },

  segmentItem: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical:
      spacing.sm,
    borderRadius:
      radius.sm,
  },

  segmentItemActive: {
    backgroundColor:
      colors.brand,
  },

  segmentText: {
    color:
      colors.onSurfaceTertiary,
    fontFamily:
      fonts.bodySemi,
    fontSize: type.base,
  },

  segmentTextActive: {
    color:
      colors.onBrand,
  },

  primaryBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    backgroundColor:
      colors.brand,
    borderRadius:
      radius.md,
    paddingVertical:
      spacing.lg,
  },

  primaryBtnText: {
    color: colors.onBrand,
    fontFamily:
      fonts.displayBold,
    fontSize: type.lg,
    letterSpacing: 0.5,
  },

  scoreRow: {
    flexDirection: "row",
    alignItems: "center",
    marginVertical: 5,
  },

  scoreLabel: {
    width: 92,
    color:
      colors.onSurfaceSecondary,
    fontFamily: fonts.body,
    fontSize: type.sm,
  },

  scoreTrack: {
    flex: 1,
    height: 8,
    backgroundColor:
      colors.surfaceTertiary,
    borderRadius: 4,
    overflow: "hidden",
    justifyContent:
      "center",
  },

  scoreCenter: {
    position: "absolute",
    left: "50%",
    width: 1,
    height: 8,
    backgroundColor:
      colors.borderStrong,
  },

  scoreFill: {
    position: "absolute",
    height: 8,
    borderRadius: 4,
  },

  scoreVal: {
    width: 40,
    textAlign: "right",
    fontFamily:
      fonts.displaySemi,
    fontSize: type.base,
  },

  state: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical:
      spacing["3xl"],
    paddingHorizontal:
      spacing.xl,
  },

  stateIcon: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor:
      colors.surfaceTertiary,
    alignItems: "center",
    justifyContent: "center",
    marginBottom:
      spacing.lg,
  },

  stateTitle: {
    color: colors.onSurface,
    fontFamily:
      fonts.displaySemi,
    fontSize: type.xl,
    textAlign: "center",
  },

  stateSub: {
    color:
      colors.onSurfaceTertiary,
    fontFamily: fonts.body,
    fontSize: type.base,
    textAlign: "center",
    marginTop: spacing.xs,
  },

  loading: {
    alignItems: "center",
    justifyContent: "center",
    padding:
      spacing["2xl"],
    gap: spacing.md,
  },

  loadingText: {
    color:
      colors.onSurfaceTertiary,
    fontFamily: fonts.body,
    fontSize: type.base,
  },

  disclaimer: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor:
      colors.brandTertiary,
    borderRadius:
      radius.sm,
    padding: spacing.md,
  },

  disclaimerText: {
    flex: 1,
    color:
      colors.brandSecondary,
    fontFamily:
      fonts.body,
    fontSize: type.sm,
    lineHeight: 17,
  },
});