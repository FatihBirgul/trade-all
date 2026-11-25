import React, { type PropsWithChildren } from "react";
import { ScrollView, TextInput, View, type TextInputProps } from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Button, Card, Failure, Label, Loading, s } from "../ui";
import { design, useTheme } from "../theme";
import { clockText } from "./presentation";
import { useBot } from "./state";

// Bot ekranlarının ortak çerçevesi. Eski Page bileşeni "DEMO / sanal işlem" şeridi gösterdiği
// için burada kullanılmaz: bu ekranlar gerçek hesabı gösterir.
export function BotPage({ children }: PropsWithChildren) {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { phase, status, heartbeatStale } = useBot();
  const banner =
    phase !== "ready" || !status
      ? null
      : heartbeatStale
        ? { text: "● BOTTAN HABER YOK · BİLGİLER ESKİ", color: colors.red }
        : status.dry_run
          ? { text: "● DENEME MODU · BOT EMİR GÖNDERMİYOR", color: colors.gold }
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

// Bağlantı yokken bot ekranlarının ortak boş durumu. Bağlıysa null döner.
export function Disconnected() {
  const { phase } = useBot();
  if (phase === "ready") return null;
  if (phase === "loading") return <Loading />;
  return (
    <Card>
      <Label>
        {phase === "revoked" ? "Bu telefonun bağlantı anahtarı artık geçerli değil." : "Bot ile bağlantı kurulmadı."}
      </Label>
      <Button title="Bağlantı sekmesine git" onPress={() => router.push("/connection")} />
    </Card>
  );
}

// Veri hiç alınamadıysa null döner; o durumu ekranlar <NoData /> ile gösterir.
export function StaleNotice() {
  const { colors } = useTheme();
  const { heartbeatStale, error, lastOkAt } = useBot();
  if (lastOkAt === null) return null;
  const updated = "Son güncelleme: " + clockText(lastOkAt) + ".";
  if (heartbeatStale)
    return (
      <Card elevated>
        <Label style={{ color: colors.red, fontWeight: "700" }}>Bottan 5 dakikadır haber yok</Label>
        <Label muted>
          Aşağıdaki bilgiler eski olabilir. {updated} Açık pozisyonların zarar durdurma (SL) emirleri Exness
          tarafında durur; sunucuyu kontrol edin.
        </Label>
      </Card>
    );
  if (error)
    return (
      <Label style={{ color: colors.red, fontSize: 13 }}>
        {error} Son bilinen bilgiler gösteriliyor. {updated}
      </Label>
    );
  return null;
}

// Bu bağlantıda henüz hiç veri alınamadı: "pozisyon yok" ya da "olay yok" demek yanlış olur.
// Veri varsa null döner.
export function NoData() {
  const { phase, lastOkAt, error, refresh } = useBot();
  if (phase !== "ready" || lastOkAt !== null) return null;
  if (!error) return <Loading />;
  return <Failure message={"Veri alınamadı. " + error} retry={() => void refresh()} />;
}
