import React from "react";
import { View } from "react-native";
import { useTheme } from "./theme";
import { Label } from "./ui";
export { SnapshotChart } from "./SnapshotChart";
export function field(value: unknown): string {
  if (typeof value === "number")
    return Number.isFinite(value)
      ? Number(value.toPrecision(6)).toLocaleString("tr-TR", {
          maximumFractionDigits: 6,
        })
      : "Veri yok";
  if (typeof value === "string" && /^-?\d+(?:\.\d+)?$/.test(value))
    return field(Number(value));
  if (typeof value === "string" && value.length <= 150) return value;
  return "Veri yok";
}
export function object(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}
export function Metrics({
  items,
}: {
  items: { name: string; value: string }[];
}) {
  const { colors } = useTheme();
  return (
    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
      {items.map((item) => (
        <View
          key={item.name}
          style={{
            flexGrow: 1,
            flexBasis: "46%",
            minWidth: 100,
            backgroundColor: colors.soft,
            borderRadius: 8,
            padding: 8,
          }}
        >
          <Label muted style={{ fontSize: 11, lineHeight: 16 }}>
            {item.name}
          </Label>
          <Label style={{ fontWeight: "700" }}>{item.value}</Label>
        </View>
      ))}
    </View>
  );
}
