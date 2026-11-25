import React, { type PropsWithChildren } from "react";
import { ScrollView, TextInput, View, type TextInputProps } from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { Label, s } from "../ui";
import { design, useTheme } from "../theme";
import { useBot } from "./state";

// Bot ekranlarının ortak çerçevesi. Eski Page bileşeni "DEMO / sanal işlem" şeridi gösterdiği
// için burada kullanılmaz: bu ekranlar gerçek hesabı gösterir.
export function BotPage({ children }: PropsWithChildren) {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { phase, status } = useBot();
  const banner =
    phase !== "ready" || !status
      ? null
      : status.dry_run
        ? { text: "● DENEME MODU · EMİR GÖNDERİLMİYOR", color: colors.gold }
        : { text: "● CANLI · GERÇEK HESAP", color: colors.green };
  return (
    <SafeAreaView testID="bot-page" edges={["top"]} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView
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
        <View style={{ width: "100%", maxWidth: 680, alignSelf: "center", gap: design.space.lg }}>
          {banner ? (
            <Label style={{ color: banner.color, fontSize: 11, fontWeight: "800", letterSpacing: 1 }}>
              {banner.text}
            </Label>
          ) : null}
          {children}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

export function BotInput(props: TextInputProps) {
  const { colors } = useTheme();
  return (
    <TextInput
      placeholderTextColor={colors.muted}
      autoCapitalize="none"
      autoCorrect={false}
      {...props}
      style={[
        {
          color: colors.text,
          backgroundColor: colors.soft,
          borderColor: colors.border,
          borderWidth: 1,
          borderRadius: 12,
          padding: 12,
          minHeight: 48,
        },
        props.style,
      ]}
    />
  );
}
