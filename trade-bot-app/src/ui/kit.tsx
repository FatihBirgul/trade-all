import React, { type PropsWithChildren } from "react";
import { ActivityIndicator, Pressable, ScrollView, Switch, Text, TextInput, View, type TextInputProps, type TextStyle, type ViewStyle } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { c, shadow } from "./theme";

type IconName = React.ComponentProps<typeof Ionicons>["name"];

export function T({ children, style, muted, size = 15, weight = "400", numberOfLines, testID }: PropsWithChildren<{ style?: TextStyle; muted?: boolean; size?: number; weight?: TextStyle["fontWeight"]; numberOfLines?: number; testID?: string }>) {
  return (
    <Text testID={testID} numberOfLines={numberOfLines} style={[{ color: muted ? c.muted : c.text, fontSize: size, fontWeight: weight, lineHeight: Math.round(size * 1.38) }, style]}>
      {children}
    </Text>
  );
}

export function Card({ children, style, testID }: PropsWithChildren<{ style?: ViewStyle; testID?: string }>) {
  return (
    <View testID={testID} style={[{ backgroundColor: c.card, borderRadius: 26, padding: 18, gap: 12 }, shadow, style]}>
      {children}
    </View>
  );
}

export function Pill({ label, color = c.hero, bg = c.tint }: { label: string; color?: string; bg?: string }) {
  return (
    <View style={{ backgroundColor: bg, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 5, alignSelf: "flex-start" }}>
      <Text style={{ color, fontSize: 12, fontWeight: "800" }}>{label}</Text>
    </View>
  );
}

type ButtonKind = "primary" | "tonal" | "danger" | "ghost" | "dangerText";
const BUTTON: Record<ButtonKind, { bg: string; fg: string }> = {
  primary: { bg: c.text, fg: c.white },
  tonal: { bg: c.tint, fg: c.hero },
  danger: { bg: c.downSoft, fg: c.down },
  ghost: { bg: "transparent", fg: c.hero },
  dangerText: { bg: "transparent", fg: c.down },
};
export function Button({ title, onPress, kind = "primary", icon, disabled = false, busy = false, testID, style }: { title: string; onPress: () => void; kind?: ButtonKind; icon?: IconName; disabled?: boolean; busy?: boolean; testID?: string; style?: ViewStyle }) {
  const look = BUTTON[kind];
  const off = disabled || busy;
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={title}
      accessibilityState={{ disabled: off, busy }}
      disabled={off}
      onPress={onPress}
      style={({ pressed }) => [
        { backgroundColor: look.bg, borderRadius: 18, minHeight: 50, paddingVertical: kind === "ghost" || kind === "dangerText" ? 8 : 14, paddingHorizontal: 16, alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 8, opacity: off ? 0.45 : pressed ? 0.75 : 1 },
        style,
      ]}
    >
      {busy ? <ActivityIndicator size="small" color={look.fg} /> : icon ? <Ionicons name={icon} size={18} color={look.fg} /> : null}
      <Text style={{ color: look.fg, fontSize: 16, fontWeight: "800" }}>{title}</Text>
    </Pressable>
  );
}

export function Row({ name, value, color, testID }: { name: string; value: string; color?: string; testID?: string }) {
  return (
    <View testID={testID} style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
      <T muted style={{ flexShrink: 1 }}>{name}</T>
      <T weight="700" style={{ color: color ?? c.text, textAlign: "right", flexShrink: 1 }}>{value}</T>
    </View>
  );
}

export function IconBubble({ icon, color, bg, size = 46 }: { icon: IconName; color: string; bg: string; size?: number }) {
  return (
    <View style={{ width: size, height: size, borderRadius: size / 2.6, backgroundColor: bg, alignItems: "center", justifyContent: "center" }}>
      <Ionicons name={icon} size={Math.round(size * 0.52)} color={color} />
    </View>
  );
}

// Üç ayrı durum: yükleniyor, hata (yeniden dene), boş. Hiçbiri diğerinin yerine kullanılmaz.
export function Loading({ label = "Yükleniyor…" }: { label?: string }) {
  return (
    <Card testID="state-loading" style={{ alignItems: "center", paddingVertical: 28 }}>
      <ActivityIndicator color={c.hero} />
      <T muted>{label}</T>
    </Card>
  );
}
export function Failure({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <Card testID="state-error" style={{ backgroundColor: c.downSoft, shadowOpacity: 0 }}>
      <View style={{ flexDirection: "row", gap: 12, alignItems: "center" }}>
        <IconBubble icon="cloud-offline" color={c.down} bg={c.white} />
        <View style={{ flex: 1 }}>
          <T weight="800" size={16}>Veri alınamadı</T>
          <T style={{ color: c.text }}>{message}</T>
        </View>
      </View>
      {retry ? <Button title="Yeniden dene" icon="refresh" kind="primary" onPress={retry} /> : null}
    </Card>
  );
}
export function Empty({ icon, title, text, children }: PropsWithChildren<{ icon: IconName; title: string; text?: string }>) {
  return (
    <Card testID="state-empty" style={{ alignItems: "center", paddingVertical: 28 }}>
      <IconBubble icon={icon} color={c.hero} bg={c.tint} size={58} />
      <T weight="800" size={17} style={{ textAlign: "center" }}>{title}</T>
      {text ? <T muted style={{ textAlign: "center" }}>{text}</T> : null}
      {children}
    </Card>
  );
}
export function Notice({ text, kind = "warn", testID }: { text: string; kind?: "warn" | "bad" | "info"; testID?: string }) {
  const look = kind === "bad" ? { bg: c.downSoft, fg: c.down, icon: "alert-circle" as const } : kind === "info" ? { bg: c.tint, fg: c.hero, icon: "information-circle" as const } : { bg: c.sunSoft, fg: c.sun, icon: "warning" as const };
  return (
    <View testID={testID} style={{ backgroundColor: look.bg, borderRadius: 18, padding: 14, flexDirection: "row", gap: 10, alignItems: "flex-start" }}>
      <Ionicons name={look.icon} size={20} color={look.fg} />
      <T style={{ flex: 1 }}>{text}</T>
    </View>
  );
}

export function Field({ label, hint, error, ...input }: TextInputProps & { label: string; hint?: string; error?: string | null }) {
  return (
    <View style={{ gap: 6 }}>
      <T weight="700" size={14}>{label}</T>
      <TextInput
        accessibilityLabel={label}
        placeholderTextColor={c.muted}
        autoCapitalize="none"
        autoCorrect={false}
        {...input}
        style={[{ backgroundColor: c.bg, borderRadius: 16, paddingHorizontal: 14, minHeight: 50, fontSize: 16, color: c.text, borderWidth: 1.5, borderColor: error ? c.down : "transparent" }, input.style]}
      />
      {error ? <T size={13} style={{ color: c.down }}>{error}</T> : hint ? <T muted size={13}>{hint}</T> : null}
    </View>
  );
}

export function Segmented<V extends string>({ options, value, onChange }: { options: readonly (readonly [V, string])[]; value: V; onChange: (value: V) => void }) {
  return (
    <View style={{ flexDirection: "row", backgroundColor: c.line, borderRadius: 18, padding: 4 }}>
      {options.map(([key, label]) => (
        <Pressable key={key} accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ selected: key === value }} onPress={() => onChange(key)} style={{ flex: 1, paddingVertical: 10, borderRadius: 14, alignItems: "center", backgroundColor: key === value ? c.card : "transparent" }}>
          <Text style={{ color: key === value ? c.hero : c.muted, fontWeight: "800", fontSize: 14 }}>{label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

export function Toggle({ label, hint, value, onChange, disabled }: { label: string; hint?: string; value: boolean; onChange: (value: boolean) => void; disabled?: boolean }) {
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
      <View style={{ flex: 1 }}>
        <T weight="700">{label}</T>
        {hint ? <T muted size={13}>{hint}</T> : null}
      </View>
      <Switch accessibilityLabel={label} value={value} onValueChange={onChange} disabled={disabled} trackColor={{ true: c.hero, false: c.line }} thumbColor={c.white} />
    </View>
  );
}

// Sekme ekranlarının ortak gövdesi: başlık + kaydırılan içerik. `hero` verilirse renkli üst alan çizilir.
export function Screen({ title, subtitle, right, hero, children, testID }: PropsWithChildren<{ title?: string; subtitle?: React.ReactNode; right?: React.ReactNode; hero?: React.ReactNode; testID?: string }>) {
  const insets = useSafeAreaInsets();
  return (
    <ScrollView testID={testID} style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ paddingBottom: 24 }} keyboardShouldPersistTaps="handled">
      {hero ? (
        <View style={{ backgroundColor: c.hero, borderBottomLeftRadius: 36, borderBottomRightRadius: 36, paddingHorizontal: 22, paddingTop: insets.top + 22, paddingBottom: 54, gap: 6 }}>{hero}</View>
      ) : (
        <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 18, paddingTop: insets.top + 22, gap: 12 }}>
          <View style={{ flex: 1 }}>
            <Text accessibilityRole="header" style={{ color: c.text, fontSize: 28, fontWeight: "900", letterSpacing: -0.5 }}>{title}</Text>
            {typeof subtitle === "string" ? <T muted size={14}>{subtitle}</T> : subtitle}
          </View>
          {right}
        </View>
      )}
      <View style={{ paddingHorizontal: 16, marginTop: hero ? -34 : 14, gap: 14, width: "100%", maxWidth: 720, alignSelf: "center" }}>{children}</View>
    </ScrollView>
  );
}
