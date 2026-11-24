import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import React from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useMarket } from "@/src/context/MarketContext";
import { colors, fonts, logoUrl, radius, spacing, type } from "@/src/theme";

export function AssetPickerModal({
  visible,
  onClose,
  onSelect,
  selected,
}: {
  visible: boolean;
  onClose: () => void;
  onSelect: (symbol: string) => void;
  selected: string;
}) {
  const { assets } = useMarket();
  const insets = useSafeAreaInsets();

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose} testID="asset-picker-backdrop" />
      <View style={[styles.sheet, { paddingBottom: insets.bottom + spacing.lg }]}>
        <View style={styles.handle} />
        <Text style={styles.title}>Select Asset</Text>
        {assets.map((a) => {
          const active = a.symbol === selected;
          return (
            <Pressable
              key={a.symbol}
              style={[styles.row, active && styles.rowActive]}
              onPress={() => {
                onSelect(a.symbol);
                onClose();
              }}
              testID={`asset-option-${a.base}`}
            >
              <Image source={{ uri: logoUrl(a.base) }} style={styles.logo} contentFit="contain" transition={150} />
              <View style={{ flex: 1 }}>
                <Text style={styles.rowName}>{a.base}/{a.quote}</Text>
                <Text style={styles.rowSub}>{a.name}</Text>
              </View>
              {active && <Ionicons name="checkmark-circle" size={22} color={colors.brand} />}
            </Pressable>
          );
        })}
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "#000000AA" },
  sheet: {
    backgroundColor: colors.surfaceSecondary,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderColor: colors.border,
  },
  handle: { alignSelf: "center", width: 40, height: 4, borderRadius: 2, backgroundColor: colors.borderStrong, marginBottom: spacing.md },
  title: { color: colors.onSurface, fontFamily: fonts.displaySemi, fontSize: type.xl, marginBottom: spacing.md },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    marginBottom: spacing.xs,
  },
  rowActive: { backgroundColor: colors.surfaceTertiary },
  logo: { width: 34, height: 34 },
  rowName: { color: colors.onSurface, fontFamily: fonts.displaySemi, fontSize: type.lg },
  rowSub: { color: colors.onSurfaceTertiary, fontFamily: fonts.body, fontSize: type.sm },
});
