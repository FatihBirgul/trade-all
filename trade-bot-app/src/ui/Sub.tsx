import React, { type PropsWithChildren } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { c } from "./theme";

// Sekmelerin üstünde açılan ekranların (Bağlantı, Elle işlem, Tanı) gövdesi: geri düğmesi + başlık.
export function goBack() {
  if (router.canGoBack()) router.back();
  else router.replace("/");
}
export function Sub({ title, children, testID }: PropsWithChildren<{ title: string; testID?: string }>) {
  const insets = useSafeAreaInsets();
  return (
    <ScrollView testID={testID} style={{ flex: 1, backgroundColor: c.bg }} contentContainerStyle={{ paddingBottom: 28 + insets.bottom }} keyboardShouldPersistTaps="handled">
      <View style={{ flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 16, paddingTop: insets.top + 18 }}>
        <Pressable testID="back" accessibilityRole="button" accessibilityLabel="Geri" onPress={goBack} style={{ width: 46, height: 46, borderRadius: 23, backgroundColor: c.card, alignItems: "center", justifyContent: "center" }}>
          <Ionicons name="arrow-back" size={22} color={c.text} />
        </Pressable>
        <Text accessibilityRole="header" style={{ color: c.text, fontSize: 24, fontWeight: "900", flex: 1 }}>{title}</Text>
      </View>
      <View style={{ paddingHorizontal: 16, marginTop: 16, gap: 14, width: "100%", maxWidth: 720, alignSelf: "center" }}>{children}</View>
    </ScrollView>
  );
}
