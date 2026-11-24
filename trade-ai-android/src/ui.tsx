import React, { useState, type PropsWithChildren } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  type TextStyle,
  useWindowDimensions,
} from "react-native";
import {
  SafeAreaView,
  useSafeAreaInsets,
} from "react-native-safe-area-context";
import { router } from "expo-router";
import {
  connectionPresentation,
  type ConnectionSnapshot,
} from "./domain/connection";
import { design, useTheme } from "./theme";
export function Label({
  children,
  muted = false,
  style,
}: PropsWithChildren<{ muted?: boolean; style?: TextStyle }>) {
  const { colors } = useTheme();
  return (
    <Text
      style={[
        {
          color: muted ? colors.muted : colors.text,
          fontSize: design.type.body,
          lineHeight: 21,
          flexShrink: 1,
        },
        style,
      ]}
    >
      {children}
    </Text>
  );
}
export function Card({
  children,
  elevated = false,
}: PropsWithChildren<{ elevated?: boolean }>) {
  const { colors } = useTheme();
  return (
    <View
      style={[
        s.card,
        {
          backgroundColor: elevated ? colors.card : colors.soft,
          borderColor: colors.border,
        },
      ]}
    >
      {children}
    </View>
  );
}
export function Heading({ children }: PropsWithChildren) {
  return (
    <Label
      style={{
        fontSize: design.type.section,
        lineHeight: 23,
        fontWeight: "700",
      }}
    >
      {children}
    </Label>
  );
}
export function Button({
  title,
  onPress,
  disabled = false,
  secondary = false,
  variant,
  accessibilityLabel,
}: {
  title: string;
  onPress: () => void;
  disabled?: boolean;
  secondary?: boolean;
  variant?: "primary" | "secondary" | "ghost";
  accessibilityLabel?: string;
}) {
  const { colors, isDark } = useTheme();
  const kind = variant ?? (secondary ? "secondary" : "primary");
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? title}
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        s.button,
        {
          backgroundColor:
            kind === "primary"
              ? colors.gold
              : kind === "secondary"
                ? colors.card
                : "transparent",
          borderColor: kind === "secondary" ? colors.border : "transparent",
          opacity: disabled ? 0.45 : pressed ? 0.7 : 1,
        },
      ]}
    >
      <Text
        style={{
          color:
            kind === "primary"
              ? isDark
                ? "#111820"
                : "#FFFFFF"
              : kind === "ghost"
                ? colors.gold
                : colors.text,
          flexShrink: 1,
          lineHeight: 21,
          fontSize: 14,
          fontWeight: "700",
          textAlign: "center",
        }}
      >
        {title}
      </Text>
    </Pressable>
  );
}
export function Choices<T extends string>({
  values,
  value,
  onChange,
  disabledValues = [],
}: {
  values: readonly T[];
  value: T | readonly T[];
  onChange: (v: T) => void;
  disabledValues?: readonly T[];
}) {
  const { colors } = useTheme();
  return (
    <View style={s.wrap}>
      {values.map((v) => {
        const disabled = disabledValues.includes(v);
        const selected =
          typeof value === "string" ? value === v : value.includes(v);
        return (
          <Pressable
            key={v}
            accessibilityRole="button"
            accessibilityState={{ selected, disabled }}
            disabled={disabled}
            onPress={() => onChange(v)}
            style={[
              s.chip,
              {
                borderColor: selected ? colors.gold : colors.border,
                backgroundColor: selected ? colors.card : colors.soft,
                opacity: disabled ? 0.45 : 1,
              },
            ]}
          >
            <Label
              style={{
                color: selected ? colors.gold : colors.muted,
                fontWeight: "600",
                fontSize: 13,
              }}
            >
              {v}
            </Label>
          </Pressable>
        );
      })}
    </View>
  );
}
export function Page({
  children,
  mode = "demo",
  headerShown = false,
  connectionError,
  connection,
}: PropsWithChildren<{
  mode?: string;
  headerShown?: boolean;
  connectionError?: string;
  connection?: ConnectionSnapshot;
}>) {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const status = connection ? connectionPresentation(connection) : null;
  return (
    <SafeAreaView
      testID="page-safe-frame"
      edges={headerShown ? ["bottom"] : ["top"]}
      style={{ flex: 1, backgroundColor: colors.bg }}
    >
      <ScrollView
        testID="page-scroll"
        style={{ flex: 1, backgroundColor: colors.bg }}
        contentContainerStyle={[
          s.content,
          {
            paddingTop: 8,
            paddingBottom: 16,
            paddingLeft: Math.max(14, insets.left + 8),
            paddingRight: Math.max(14, insets.right + 8),
          },
        ]}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
      >
        <View
          style={{
            width: "100%",
            maxWidth: 680,
            alignSelf: "center",
            gap: design.space.lg,
          }}
        >
          <Label
            style={{
              color: colors.gold,
              fontSize: 11,
              fontWeight: "800",
              letterSpacing: 1,
            }}
          >
            {mode === "demo"
              ? "● DEMO · ÖRNEK VERİ"
              : "● CANLI VERİ MODU · YALNIZ SANAL İŞLEMLER"}
          </Label>
          {status ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Bağlantı ayrıntılarını aç"
              onPress={() => router.push("/settings")}
              style={{ minHeight: 48, justifyContent: "center" }}
            >
              <Label
                style={{
                  fontSize: 12,
                  color:
                    mode === "live" && status.attention
                      ? colors.red
                      : colors.muted,
                }}
              >
                {status.title} · Ayarlar
              </Label>
            </Pressable>
          ) : connectionError ? (
            <Label muted style={{ fontSize: 12 }}>
              Bağlantı doğrulanamadı · Ayarlar’dan kontrol edin.
            </Label>
          ) : null}
          {children}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
export function Row({ name, value }: { name: string; value: string }) {
  const { width, fontScale } = useWindowDimensions();
  const stacked = width / fontScale < 360;
  return (
    <View
      testID={"row-" + name}
      style={[s.row, stacked && { flexDirection: "column", gap: 2 }]}
    >
      <Label
        muted
        style={stacked ? { width: "100%" } : { flex: 1, minWidth: 0 }}
      >
        {name}
      </Label>
      <Label
        style={{
          fontWeight: "600",
          fontVariant: ["tabular-nums"],
          ...(stacked
            ? { width: "100%" as const }
            : { flex: 1, minWidth: 0, textAlign: "right" as const }),
        }}
      >
        {value}
      </Label>
    </View>
  );
}
export function Loading() {
  const { colors } = useTheme();
  return (
    <View
      accessibilityRole="progressbar"
      accessibilityLabel="Veriler yükleniyor"
      style={{
        minHeight: 48,
        flexDirection: "row",
        alignItems: "center",
        gap: 12,
        paddingVertical: 10,
      }}
    >
      <ActivityIndicator color={colors.muted} size="small" />
      <Label muted>Yükleniyor…</Label>
    </View>
  );
}
export function Empty({ text = "Henüz kayıt yok." }: { text?: string }) {
  return (
    <Card>
      <Label muted>{text}</Label>
    </Card>
  );
}
export function Failure({
  message,
  retry,
}: {
  message: string;
  retry: () => void;
}) {
  const { colors } = useTheme();
  return (
    <Card>
      <Label style={{ color: colors.red }}>{message}</Label>
      <Button title="Yeniden dene" onPress={retry} secondary />
    </Card>
  );
}
export const s = StyleSheet.create({
  content: { paddingHorizontal: 14, paddingTop: 10 },
  card: {
    padding: design.space.lg,
    borderWidth: 1,
    borderRadius: design.radius.card,
    gap: design.space.md,
  },
  button: {
    minHeight: 48,
    justifyContent: "center",
    borderRadius: 14,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderWidth: 1,
  },
  wrap: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  chip: {
    minHeight: 48,
    maxWidth: "100%",
    flexShrink: 1,
    justifyContent: "center",
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderWidth: 1,
    borderRadius: 12,
  },
  row: {
    flexDirection: "row",
    gap: 8,
    alignItems: "flex-start",
    paddingVertical: 2,
  },
});

export function ScreenHeader({
  title,
  subtitle,
  badge,
}: {
  title: string;
  subtitle?: string;
  badge?: string;
}) {
  const { colors } = useTheme();
  return (
    <View style={{ gap: 6, paddingVertical: 4 }}>
      {badge ? (
        <Label
          style={{
            color: colors.gold,
            fontWeight: "800",
            fontSize: 12,
            letterSpacing: 1.5,
          }}
        >
          {badge}
        </Label>
      ) : null}
      <Label
        style={{
          fontSize: design.type.title,
          lineHeight: 30,
          fontWeight: "800",
          letterSpacing: -0.6,
        }}
      >
        {title}
      </Label>
      {subtitle ? <Label muted>{subtitle}</Label> : null}
    </View>
  );
}
export function SectionHeader({
  title,
  action,
  onPress,
}: {
  title: string;
  action?: string;
  onPress?: () => void;
}) {
  const { width, fontScale } = useWindowDimensions();
  return (
    <View
      style={{
        flexDirection: width / fontScale < 360 ? "column" : "row",
        alignItems: "flex-start",
        justifyContent: "space-between",
        gap: 4,
      }}
    >
      <View style={{ flex: 1, minWidth: 0 }}>
        <Heading>{title}</Heading>
      </View>
      {action && onPress ? (
        <Button title={action} onPress={onPress} variant="ghost" />
      ) : null}
    </View>
  );
}

export function Disclosure({
  title,
  children,
  initiallyOpen = false,
}: PropsWithChildren<{ title: string; initiallyOpen?: boolean }>) {
  const [open, setOpen] = useState(initiallyOpen);
  const { colors } = useTheme();
  return (
    <View style={{ gap: 6 }}>
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        onPress={() => setOpen((v) => !v)}
        style={{ minHeight: 48, justifyContent: "center" }}
      >
        <Label style={{ color: colors.text, fontWeight: "600" }}>
          {title} {open ? "−" : "+"}
        </Label>
      </Pressable>
      {open ? children : null}
    </View>
  );
}
